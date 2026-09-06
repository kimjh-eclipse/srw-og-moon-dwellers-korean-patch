#!/usr/bin/env python3
"""빠른 패처(C#)에 「세이브 목록 한글화」 기능을 추가한다.

- PARAM.SFO 의 SUB_TITLE·DETAIL 프록시 코드 → 한글 (ogmd_save_hangul.py 와 같은 로직)
- 역매핑 표는 리소스 OGMD_SAVE_proxymap.tsv 로 EXE 에 내장 (csc /resource)
- 대상: <RPCS3>\\dev_hdd0\\home\\*\\savedata\\BLJS10335_OMI-*\\PARAM.SFO
- 백업: <savedata 상위>\\ogmd_sfo_backup_<시각>\\<세이브폴더>\\PARAM.SFO (세이브 폴더 안에는 파일을 만들지 않음)
C# 5 (csc v4.0.30319) 문법만 사용.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent
CS = ROOT / "iso_quickpatch" / "OGMDIsoQuickPatch.cs"


def insert_after(text: str, anchor: str, addition: str) -> str:
    if text.count(anchor) != 1:
        raise AssertionError("anchor not unique: " + anchor[:60])
    return text.replace(anchor, anchor + addition, 1)


def insert_before(text: str, anchor: str, addition: str) -> str:
    if text.count(anchor) != 1:
        raise AssertionError("anchor not unique: " + anchor[:60])
    return text.replace(anchor, addition + anchor, 1)


def main() -> None:
    raw = CS.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    t = raw.decode("utf-8-sig")
    if "SaveHangul" in t:
        print("이미 적용됨")
        return

    # 1) 상수·열거형
    t = insert_after(t, '    private const string PatchResourceName = "OGMD_ISO_ranges.bin";\n',
                     '    private const string SaveMapResourceName = "OGMD_SAVE_proxymap.tsv";\n'
                     '    private const string SaveDirectoryPrefix = "BLJS10335_OMI-";\n')
    t = t.replace("        DirectVerify,\n        DirectPatch\n    }",
                  "        DirectVerify,\n        DirectPatch,\n        SaveHangul\n    }", 1)

    # 2) 작업 항목·결과 필드
    t = insert_after(t, "        public string DirectTargetPath;\n        public bool DirectBackup;\n    }",
                     "")
    t = t.replace("        public string DirectTargetPath;\n        public bool DirectBackup;\n    }\n",
                  "        public string DirectTargetPath;\n        public bool DirectBackup;\n        public string SaveRoot;\n    }\n", 1)
    t = t.replace("        public bool Rpcs3Inspected;\n        public string DirectTargetPath;\n    }\n",
                  "        public bool Rpcs3Inspected;\n        public string DirectTargetPath;\n        public int SaveCount;\n        public string SaveBackupRoot;\n    }\n", 1)

    # 3) 폼 필드·버튼
    t = insert_after(t, "        private readonly Button directPatchButton;\n",
                     "        private readonly Button saveHangulButton;\n")
    t = insert_after(t, "            directPatchButton.Click += delegate { StartDirectOperation(UiOperation.DirectPatch); };\n            Controls.Add(directPatchButton);\n",
                     '''
            saveHangulButton = new Button();
            saveHangulButton.Text = "세이브 목록 한글화 (PARAM.SFO)";
            saveHangulButton.SetBounds(449, 775, 230, 38);
            saveHangulButton.Click += delegate { StartSaveHangul(); };
            Controls.Add(saveHangulButton);
''')
    t = insert_after(t, "            directPatchButton.Enabled = !busy;\n",
                     "            saveHangulButton.Enabled = !busy;\n")

    # 4) 시작 메서드 (StartOperation 앞에 삽입)
    t = insert_before(t, "        private void StartOperation(UiOperation operation)\n", '''        private void StartSaveHangul()
        {
            string root;
            try
            {
                root = ResolveRpcs3RootForSaves(rpcs3PathBox.Text.Trim().Trim('"'));
            }
            catch (Exception ex)
            {
                MessageBox.Show(this, ex.Message, "RPCS3 경로 확인", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            DialogResult answer = MessageBox.Show(this,
                "다음 RPCS3의 세이브 목록 문구를 한글로 바꿉니다:\\r\\n\\r\\n" + root +
                "\\r\\n\\r\\n대상은 dev_hdd0\\\\home\\\\*\\\\savedata\\\\" + SaveDirectoryPrefix + "* 폴더의 PARAM.SFO 안\\r\\n" +
                "SUB_TITLE·DETAIL 문자열만입니다. 게임 세이브 본체(.SAV)는 건드리지 않습니다.\\r\\n" +
                "원본 PARAM.SFO 는 savedata 상위 폴더의 ogmd_sfo_backup_* 에 백업합니다.\\r\\n\\r\\n" +
                "게임이 새로 저장하면 그 세이브는 다시 대체 코드로 기록되므로, 필요할 때마다 다시 실행하세요.\\r\\n\\r\\n" +
                "RPCS3가 완전히 종료되었습니까?",
                "세이브 목록 한글화 확인", MessageBoxButtons.YesNo, MessageBoxIcon.Question, MessageBoxDefaultButton.Button2);
            if (answer != DialogResult.Yes)
                return;

            logBox.Clear();
            SetBusy(true, "세이브 목록 한글화 중...");
            worker.RunWorkerAsync(new UiWorkItem
            {
                Operation = UiOperation.SaveHangul,
                SaveRoot = root
            });
        }

        private static string ResolveRpcs3RootForSaves(string selectedPath)
        {
            if (String.IsNullOrWhiteSpace(selectedPath) || !Directory.Exists(selectedPath))
                throw new DirectoryNotFoundException(
                    "RPCS3 폴더(rpcs3.exe 와 dev_hdd0 가 있는 폴더)를 'RPCS3 / 폴더형 게임 경로'에 지정하세요.");
            DirectoryInfo current = new DirectoryInfo(Path.GetFullPath(selectedPath));
            while (current != null)
            {
                if (Directory.Exists(Path.Combine(current.FullName, "dev_hdd0", "home")))
                    return current.FullName.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
                current = current.Parent;
            }
            throw new DirectoryNotFoundException(
                "선택한 경로에서 RPCS3 의 dev_hdd0\\\\home 을 찾지 못했습니다.\\r\\n" +
                "RPCS3 루트 폴더(또는 그 안의 dev_hdd0\\\\game\\\\BLJS10335 경로)를 선택하세요.");
        }

''')

    # 5) WorkerDoWork 분기
    t = t.replace(
        "                if (work.Operation == UiOperation.DirectVerify || work.Operation == UiOperation.DirectPatch)\n"
        "                {\n"
        "                    result.ExitCode = RunDirectFolderScript(work.Operation, work.DirectTargetPath, work.DirectBackup);\n"
        "                }\n",
        "                if (work.Operation == UiOperation.SaveHangul)\n"
        "                {\n"
        "                    string backupRoot;\n"
        "                    result.SaveCount = RunSaveHangul(work.SaveRoot, out backupRoot);\n"
        "                    result.SaveBackupRoot = backupRoot;\n"
        "                    result.ExitCode = 0;\n"
        "                }\n"
        "                else if (work.Operation == UiOperation.DirectVerify || work.Operation == UiOperation.DirectPatch)\n"
        "                {\n"
        "                    result.ExitCode = RunDirectFolderScript(work.Operation, work.DirectTargetPath, work.DirectBackup);\n"
        "                }\n", 1)

    # 6) 완료 메시지
    t = insert_before(t, "            else if (result.Operation == UiOperation.DirectVerify)\n", '''            else if (result.Operation == UiOperation.SaveHangul)
            {
                MessageBox.Show(this,
                    result.SaveCount > 0 ?
                        "세이브 " + result.SaveCount + "개의 목록 문구를 한글로 바꿨습니다.\\r\\n\\r\\n백업: " + result.SaveBackupRoot +
                        "\\r\\n\\r\\nRPCS3 세이브 목록과 게임 내 불러오기 화면에서 확인하세요." :
                        "바꿀 세이브가 없습니다. 이미 한글이거나 OGMD 세이브가 없습니다.",
                    "세이브 목록 한글화 완료", MessageBoxButtons.OK, MessageBoxIcon.Information);
            }
''')

    # 7) 정적 구현부 (LoadPack 앞에 삽입)
    t = insert_before(t, "    private static List<PackFile> LoadPack()\n", r'''    private sealed class SfoEntry
    {
        public string Key;
        public ushort Format;
        public uint Length;
        public uint Maximum;
        public byte[] Data;
    }

    private static Dictionary<char, char> LoadSaveMap()
    {
        Stream resource = Assembly.GetExecutingAssembly().GetManifestResourceStream(SaveMapResourceName);
        if (resource == null)
            throw new InvalidDataException("실행 파일 내부 세이브 문자 표를 찾을 수 없습니다.");
        Dictionary<char, char> table = new Dictionary<char, char>();
        using (resource)
        using (StreamReader reader = new StreamReader(resource, Encoding.UTF8))
        {
            string line;
            bool header = true;
            while ((line = reader.ReadLine()) != null)
            {
                if (header) { header = false; continue; }
                if (line.Length == 0) continue;
                string[] parts = line.Split('\t');
                if (parts.Length < 2) continue;
                int code = Convert.ToInt32(parts[0].Substring(2), 16);
                if (code > 0xFFFF || parts[1].Length != 1)
                    throw new InvalidDataException("세이브 문자 표 형식 오류: " + line);
                table[(char)code] = parts[1][0];
            }
        }
        if (table.Count < 1000)
            throw new InvalidDataException("세이브 문자 표가 비정상적으로 작습니다: " + table.Count);
        return table;
    }

    private static List<SfoEntry> ParseSfo(byte[] blob)
    {
        if (blob.Length < 0x14 || blob[0] != 0 || blob[1] != (byte)'P' || blob[2] != (byte)'S' || blob[3] != (byte)'F')
            throw new InvalidDataException("PARAM.SFO 형식이 아닙니다.");
        uint keyOff = BitConverter.ToUInt32(blob, 8);
        uint dataOff = BitConverter.ToUInt32(blob, 12);
        uint count = BitConverter.ToUInt32(blob, 16);
        List<SfoEntry> entries = new List<SfoEntry>();
        for (int i = 0; i < count; i++)
        {
            int at = 0x14 + 16 * i;
            ushort kOff = BitConverter.ToUInt16(blob, at);
            ushort fmt = BitConverter.ToUInt16(blob, at + 2);
            uint len = BitConverter.ToUInt32(blob, at + 4);
            uint max = BitConverter.ToUInt32(blob, at + 8);
            uint dOff = BitConverter.ToUInt32(blob, at + 12);
            int keyStart = (int)(keyOff + kOff);
            int keyEnd = Array.IndexOf(blob, (byte)0, keyStart);
            SfoEntry e = new SfoEntry();
            e.Key = Encoding.UTF8.GetString(blob, keyStart, keyEnd - keyStart);
            e.Format = fmt;
            e.Length = len;
            e.Maximum = max;
            e.Data = new byte[max];
            Array.Copy(blob, (int)(dataOff + dOff), e.Data, 0, (int)max);
            entries.Add(e);
        }
        return entries;
    }

    private static byte[] BuildSfo(List<SfoEntry> entries)
    {
        MemoryStream keys = new MemoryStream();
        List<int> keyOffsets = new List<int>();
        foreach (SfoEntry e in entries)
        {
            keyOffsets.Add((int)keys.Length);
            byte[] k = Encoding.UTF8.GetBytes(e.Key);
            keys.Write(k, 0, k.Length);
            keys.WriteByte(0);
        }
        while (keys.Length % 4 != 0)
            keys.WriteByte(0);
        MemoryStream data = new MemoryStream();
        List<int> dataOffsets = new List<int>();
        foreach (SfoEntry e in entries)
        {
            dataOffsets.Add((int)data.Length);
            byte[] chunk = new byte[e.Maximum];
            Array.Copy(e.Data, chunk, Math.Min(e.Data.Length, chunk.Length));
            data.Write(chunk, 0, chunk.Length);
        }
        int headerSize = 0x14 + 16 * entries.Count;
        MemoryStream out_ = new MemoryStream();
        BinaryWriter w = new BinaryWriter(out_);
        w.Write(new byte[] { 0, (byte)'P', (byte)'S', (byte)'F' });
        w.Write((uint)0x101);
        w.Write((uint)headerSize);
        w.Write((uint)(headerSize + keys.Length));
        w.Write((uint)entries.Count);
        for (int i = 0; i < entries.Count; i++)
        {
            w.Write((ushort)keyOffsets[i]);
            w.Write(entries[i].Format);
            w.Write(entries[i].Length);
            w.Write(entries[i].Maximum);
            w.Write((uint)dataOffsets[i]);
        }
        w.Write(keys.ToArray());
        w.Write(data.ToArray());
        w.Flush();
        return out_.ToArray();
    }

    private static string DecodeSaveText(string text, Dictionary<char, char> table)
    {
        StringBuilder sb = new StringBuilder(text.Length);
        foreach (char ch in text)
        {
            char mapped;
            sb.Append(table.TryGetValue(ch, out mapped) ? mapped : ch);
        }
        return sb.ToString();
    }

    // 반환: 새 SFO 바이트(변경 없으면 null). 원본 배치를 바이트 단위로 재현할 수 없으면 예외.
    private static byte[] ConvertSaveSfo(byte[] blob, Dictionary<char, char> table, List<string> log)
    {
        List<SfoEntry> entries = ParseSfo(blob);
        byte[] rebuilt = BuildSfo(entries);
        if (!rebuilt.SequenceEqual(blob))
            throw new InvalidDataException("SFO 재조립이 원본과 다릅니다 — 이 파일은 건너뜁니다.");
        bool changed = false;
        foreach (SfoEntry e in entries)
        {
            if (e.Format != 0x0204 || (e.Key != "SUB_TITLE" && e.Key != "DETAIL"))
                continue;
            int len = (int)e.Length;
            while (len > 0 && e.Data[len - 1] == 0) len--;
            string before = Encoding.UTF8.GetString(e.Data, 0, len);
            string after = DecodeSaveText(before, table);
            if (after == before)
                continue;
            byte[] encoded = Encoding.UTF8.GetBytes(after);
            if (encoded.Length + 1 > e.Maximum)
                throw new InvalidDataException(e.Key + ": 한글 문자열이 필드 최대 길이를 넘습니다.");
            e.Data = new byte[e.Maximum];
            Array.Copy(encoded, e.Data, encoded.Length);
            e.Length = (uint)(encoded.Length + 1);
            changed = true;
            log.Add("    " + e.Key + ": " + after.Replace("\n", " | "));
        }
        return changed ? BuildSfo(entries) : null;
    }

    private static int RunSaveHangul(string rpcs3Root, out string backupRootOut)
    {
        Dictionary<char, char> table = LoadSaveMap();
        string homeRoot = Path.Combine(rpcs3Root, "dev_hdd0", "home");
        if (!Directory.Exists(homeRoot))
            throw new DirectoryNotFoundException("dev_hdd0\\home 이 없습니다: " + homeRoot);
        Console.WriteLine("[세이브 목록 한글화] " + rpcs3Root);
        string stamp = DateTime.Now.ToString("yyyyMMdd_HHmmss");
        int converted = 0;
        backupRootOut = null;
        foreach (string user in Directory.GetDirectories(homeRoot))
        {
            string saveRoot = Path.Combine(user, "savedata");
            if (!Directory.Exists(saveRoot))
                continue;
            string backupRoot = Path.Combine(user, "ogmd_sfo_backup_" + stamp);
            foreach (string save in Directory.GetDirectories(saveRoot, SaveDirectoryPrefix + "*"))
            {
                string sfoPath = Path.Combine(save, "PARAM.SFO");
                if (!File.Exists(sfoPath))
                    continue;
                string name = Path.GetFileName(save);
                List<string> log = new List<string>();
                byte[] rebuilt;
                try
                {
                    rebuilt = ConvertSaveSfo(File.ReadAllBytes(sfoPath), table, log);
                }
                catch (Exception ex)
                {
                    Console.WriteLine("[건너뜀] " + name + ": " + ex.Message);
                    continue;
                }
                if (rebuilt == null)
                {
                    Console.WriteLine("[변경 없음] " + name);
                    continue;
                }
                string backupDir = Path.Combine(backupRoot, name);
                Directory.CreateDirectory(backupDir);
                File.Copy(sfoPath, Path.Combine(backupDir, "PARAM.SFO"), true);
                DateTime stampTime = File.GetLastWriteTimeUtc(sfoPath);
                File.WriteAllBytes(sfoPath, rebuilt);
                File.SetLastWriteTimeUtc(sfoPath, stampTime);
                converted++;
                backupRootOut = backupRoot;
                Console.WriteLine("[적용] " + name);
                foreach (string line in log)
                    Console.WriteLine(line);
            }
        }
        WriteOk("세이브 " + converted + "개 변환" + (backupRootOut != null ? ", 백업: " + backupRootOut : String.Empty));
        return converted;
    }

''')

    # 8) CLI: --save-hangul <RPCS3 루트>  (ISO 없이 세이브 목록 한글화만 실행)
    t = t.replace("        public string Rpcs3Path;\n        public bool DeleteInstalledGame;\n    }\n",
                  "        public string Rpcs3Path;\n        public bool DeleteInstalledGame;\n        public string SaveHangulRoot;\n    }\n", 1)
    t = insert_before(t, '            else if (arg.StartsWith("--", StringComparison.Ordinal))\n                throw new ArgumentException("알 수 없는 옵션입니다: " + arg);\n', '''            else if (arg.Equals("--save-hangul", StringComparison.OrdinalIgnoreCase))
            {
                if (index + 1 >= args.Length)
                    throw new ArgumentException("--save-hangul 다음에 RPCS3 폴더 경로를 지정하세요.");
                options.SaveHangulRoot = args[++index].Trim().Trim('"');
            }
''')
    t = t.replace("        if (String.IsNullOrWhiteSpace(options.IsoPath))\n        {\n            using (OpenFileDialog dialog = new OpenFileDialog())\n",
                  "        if (!String.IsNullOrWhiteSpace(options.SaveHangulRoot))\n            return options;\n\n"
                  "        if (String.IsNullOrWhiteSpace(options.IsoPath))\n        {\n            using (OpenFileDialog dialog = new OpenFileDialog())\n", 1)
    t = t.replace("    private static int Run(Options options)\n    {\n        WriteHeader();\n",
                  "    private static int Run(Options options)\n    {\n        WriteHeader();\n"
                  "        if (!String.IsNullOrWhiteSpace(options.SaveHangulRoot))\n        {\n"
                  "            if (Process.GetProcessesByName(\"rpcs3\").Length != 0)\n"
                  "                throw new InvalidOperationException(\"RPCS3가 실행 중입니다. 완전히 종료한 뒤 다시 실행하세요.\");\n"
                  "            string backupRoot;\n"
                  "            RunSaveHangul(Path.GetFullPath(options.SaveHangulRoot), out backupRoot);\n"
                  "            return 0;\n        }\n", 1)
    assert t.count("SaveHangulRoot") == 5, t.count("SaveHangulRoot")

    CS.write_bytes((b"\xef\xbb\xbf" if bom else b"") + t.encode("utf-8"))
    print("C# 패치 적용:", CS)


if __name__ == "__main__":
    main()
