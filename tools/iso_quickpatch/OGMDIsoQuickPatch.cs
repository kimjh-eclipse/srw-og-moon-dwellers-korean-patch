using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.MemoryMappedFiles;
using System.Linq;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Windows.Forms;

internal static class OGMDIsoQuickPatch
{
    private const int SectorSize = 2048;
        private const string VersionText = "v20260816-plain-labels-options-gui";
    private const string PatchResourceName = "OGMD_ISO_ranges.bin";
    private const string PackMagic = "OGMDRNG1";
    private const string BackupMagic = "OGMDBAK1";
    private const int FormatVersion = 1;
    private const int LegacyBackupFormatVersion = 1;
    private const int BackupFormatVersion = 2;
    private const int BackupFooterHashSize = 32;
    private const uint AttachParentProcess = 0xFFFFFFFF;

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool AttachConsole(uint processId);

    private sealed class PatchRange
    {
        public long LogicalOffset;
        public byte[] Data;
    }

    private sealed class PackFile
    {
        public string IsoPath;
        public long Size;
        public byte[] SourceHash;
        public byte[] TargetHash;
        public List<PatchRange> Ranges = new List<PatchRange>();
    }

    private sealed class IsoRecord
    {
        public string Name;
        public uint Extent;
        public uint Size;
        public bool IsDirectory;
        public bool IsMultiExtent;
        public int FileUnitSize;
        public int InterleaveGap;
    }

    private sealed class IsoExtent
    {
        public long Offset;
        public long Size;
        public uint Lba;
    }

    private sealed class LocatedFile
    {
        public PackFile Patch;
        public List<IsoExtent> Extents = new List<IsoExtent>();
    }

    private sealed class PhysicalSegment
    {
        public long AbsoluteOffset;
        public byte[] Data;
        public int DataOffset;
        public int Length;
    }

    private enum FileState
    {
        Source,
        Target,
        Unknown
    }

    private sealed class Options
    {
        public string IsoPath;
        public string BackupPath;
        public bool Yes;
        public bool VerifyOnly;
        public bool Restore;
        public bool Pause;
        public string Rpcs3Path;
        public bool DeleteInstalledGame;
    }

    private enum UiOperation
    {
        Verify,
        Patch,
        Restore
    }

    private sealed class UiResult
    {
        public int ExitCode;
        public Exception Error;
        public UiOperation Operation;
        public bool DeleteInstalledGame;
        public bool Rpcs3Inspected;
    }

    private sealed class UiTextWriter : TextWriter
    {
        private readonly Action<string> append;

        public UiTextWriter(Action<string> appendText)
        {
            append = appendText;
        }

        public override Encoding Encoding { get { return Encoding.UTF8; } }

        public override void Write(string value)
        {
            if (!String.IsNullOrEmpty(value))
                append(value);
        }

        public override void Write(char value)
        {
            append(value.ToString());
        }

        public override void WriteLine(string value)
        {
            append((value ?? String.Empty) + Environment.NewLine);
        }

        public override void WriteLine()
        {
            append(Environment.NewLine);
        }
    }

    private sealed class MainForm : Form
    {
        private readonly TextBox isoPathBox;
        private readonly Button browseButton;
        private readonly TextBox backupPathBox;
        private readonly Button backupBrowseButton;
        private readonly TextBox rpcs3PathBox;
        private readonly Button rpcs3BrowseButton;
        private readonly CheckBox deleteInstalledGameCheck;
        private readonly CheckBox warningCheck;
        private readonly Button verifyButton;
        private readonly Button patchButton;
        private readonly Button restoreButton;
        private readonly Button closeButton;
        private readonly RichTextBox logBox;
        private readonly ProgressBar progressBar;
        private readonly Label statusLabel;
        private readonly BackgroundWorker worker;
        private bool busyState;
        private bool backupPathCustomized;

        public MainForm(string initialIsoPath)
        {
            Text = "OGMD 한국어 ISO 빠른 패처 " + VersionText;
            StartPosition = FormStartPosition.CenterScreen;
            FormBorderStyle = FormBorderStyle.FixedSingle;
            MaximizeBox = false;
            ClientSize = new Size(900, 872);
            Font = new Font("Segoe UI", 9F);
            BackColor = Color.FromArgb(242, 246, 250);
            AllowDrop = true;

            Panel titlePanel = new Panel();
            titlePanel.SetBounds(0, 0, 900, 78);
            titlePanel.BackColor = Color.FromArgb(17, 55, 86);
            Controls.Add(titlePanel);

            Label title = new Label();
            title.Text = "OG 문 드웰러즈 한국어 ISO 빠른 패처";
            title.ForeColor = Color.White;
            title.Font = new Font("Segoe UI", 18F, FontStyle.Bold);
            title.AutoSize = true;
            title.Location = new Point(24, 13);
            titlePanel.Controls.Add(title);

            Label subtitle = new Label();
            subtitle.Text = "11.8GB 전체 복사 없이 ISO 내부의 변경 구간만 직접 패치합니다.";
            subtitle.ForeColor = Color.FromArgb(205, 226, 242);
            subtitle.AutoSize = true;
            subtitle.Location = new Point(27, 51);
            titlePanel.Controls.Add(subtitle);

            Label isoLabel = new Label();
            isoLabel.Text = "ISO 파일";
            isoLabel.Font = new Font("Segoe UI", 9F, FontStyle.Bold);
            isoLabel.AutoSize = true;
            isoLabel.Location = new Point(22, 96);
            Controls.Add(isoLabel);

            isoPathBox = new TextBox();
            isoPathBox.SetBounds(22, 118, 750, 27);
            isoPathBox.Text = initialIsoPath ?? String.Empty;
            Controls.Add(isoPathBox);

            browseButton = new Button();
            browseButton.Text = "찾아보기...";
            browseButton.SetBounds(782, 116, 96, 30);
            browseButton.Click += delegate { BrowseIso(); };
            Controls.Add(browseButton);

            Label backupLabel = new Label();
            backupLabel.Text = "복구 백업 파일 (기존 백업 선택 가능)";
            backupLabel.Font = new Font("Segoe UI", 9F, FontStyle.Bold);
            backupLabel.AutoSize = true;
            backupLabel.Location = new Point(22, 154);
            Controls.Add(backupLabel);

            backupPathBox = new TextBox();
            backupPathBox.SetBounds(22, 176, 750, 27);
            backupPathBox.Text = String.IsNullOrWhiteSpace(initialIsoPath) ? String.Empty :
                Path.GetFullPath(initialIsoPath) + ".ogmd-backup";
            backupPathBox.TextChanged += delegate
            {
                if (backupPathBox.Focused)
                    backupPathCustomized = true;
            };
            Controls.Add(backupPathBox);

            backupBrowseButton = new Button();
            backupBrowseButton.Text = "찾아보기...";
            backupBrowseButton.SetBounds(782, 174, 96, 30);
            backupBrowseButton.Click += delegate { BrowseBackup(); };
            Controls.Add(backupBrowseButton);
            isoPathBox.TextChanged += delegate { UpdateDefaultBackupPath(); };

            Label rpcs3Label = new Label();
            rpcs3Label.Text = "RPCS3 폴더 (선택 사항)";
            rpcs3Label.Font = new Font("Segoe UI", 9F, FontStyle.Bold);
            rpcs3Label.AutoSize = true;
            rpcs3Label.Location = new Point(22, 212);
            Controls.Add(rpcs3Label);

            rpcs3PathBox = new TextBox();
            rpcs3PathBox.SetBounds(22, 234, 750, 27);
            Controls.Add(rpcs3PathBox);

            rpcs3BrowseButton = new Button();
            rpcs3BrowseButton.Text = "찾아보기...";
            rpcs3BrowseButton.SetBounds(782, 232, 96, 30);
            rpcs3BrowseButton.Click += delegate { BrowseRpcs3(); };
            Controls.Add(rpcs3BrowseButton);

            deleteInstalledGameCheck = new CheckBox();
            deleteInstalledGameCheck.Text = "패치 성공 후 dev_hdd0\\game\\BLJS10335 기존 설치 데이터만 삭제";
            deleteInstalledGameCheck.Font = new Font("Segoe UI", 9F, FontStyle.Bold);
            deleteInstalledGameCheck.AutoSize = true;
            deleteInstalledGameCheck.Location = new Point(22, 269);
            Controls.Add(deleteInstalledGameCheck);

            GroupBox warningGroup = new GroupBox();
            warningGroup.Text = "반드시 확인할 주의사항";
            warningGroup.Font = new Font("Segoe UI", 10F, FontStyle.Bold);
            warningGroup.ForeColor = Color.FromArgb(123, 72, 0);
            warningGroup.BackColor = Color.FromArgb(255, 248, 220);
            warningGroup.SetBounds(22, 299, 856, 220);
            Controls.Add(warningGroup);

            Label warnings = new Label();
            warnings.Font = new Font("Segoe UI", 9.5F, FontStyle.Regular);
            warnings.ForeColor = Color.FromArgb(70, 48, 10);
            warnings.AutoSize = false;
            warnings.SetBounds(18, 28, 820, 145);
            warnings.Text =
                "1. 복호화된 일본판 BLJS10335 ISO만 지원합니다. 암호화 ISO나 다른 판본에는 적용하지 마세요.\r\n" +
                "2. 선택한 ISO 파일 자체를 수정합니다. 작업 중 RPCS3를 완전히 종료하고 ISO 마운트도 해제하세요.\r\n" +
                "3. 기존 백업은 같은 경로에서 현재 버전용으로 갱신됩니다. 별도 백업은 만들지 않습니다.\r\n" +
                "4. 설치 데이터 삭제 옵션은 선택한 RPCS3의 dev_hdd0\\game\\BLJS10335 폴더 하나만 삭제합니다.\r\n" +
                "5. 세이브·savestate·캐시(PPU/SPU/셰이더)와 BLJS10335.pre_* 폴더는 삭제하지 않습니다.";
            warningGroup.Controls.Add(warnings);

            warningCheck = new CheckBox();
            warningCheck.Text = "위 주의사항을 확인했으며, 선택한 ISO가 직접 수정되는 것에 동의합니다.";
            warningCheck.Font = new Font("Segoe UI", 9F, FontStyle.Bold);
            warningCheck.AutoSize = true;
            warningCheck.Location = new Point(20, 179);
            warningGroup.Controls.Add(warningCheck);

            Label logLabel = new Label();
            logLabel.Text = "진행 로그";
            logLabel.Font = new Font("Segoe UI", 9F, FontStyle.Bold);
            logLabel.AutoSize = true;
            logLabel.Location = new Point(22, 534);
            Controls.Add(logLabel);

            logBox = new RichTextBox();
            logBox.SetBounds(22, 557, 856, 176);
            logBox.ReadOnly = true;
            logBox.BackColor = Color.FromArgb(22, 28, 34);
            logBox.ForeColor = Color.FromArgb(225, 235, 240);
            logBox.Font = new Font("Consolas", 9F);
            logBox.WordWrap = false;
            Controls.Add(logBox);

            verifyButton = new Button();
            verifyButton.Text = "원본 검사";
            verifyButton.SetBounds(22, 749, 120, 38);
            verifyButton.Click += delegate { StartOperation(UiOperation.Verify); };
            Controls.Add(verifyButton);

            patchButton = new Button();
            patchButton.Text = "ISO에 한국어 패치 적용";
            patchButton.Font = new Font("Segoe UI", 9F, FontStyle.Bold);
            patchButton.BackColor = Color.FromArgb(34, 112, 166);
            patchButton.ForeColor = Color.White;
            patchButton.FlatStyle = FlatStyle.Flat;
            patchButton.SetBounds(153, 749, 214, 38);
            patchButton.Click += delegate { StartOperation(UiOperation.Patch); };
            Controls.Add(patchButton);

            restoreButton = new Button();
            restoreButton.Text = "원본으로 복구";
            restoreButton.SetBounds(378, 749, 140, 38);
            restoreButton.Click += delegate { StartOperation(UiOperation.Restore); };
            Controls.Add(restoreButton);

            closeButton = new Button();
            closeButton.Text = "닫기";
            closeButton.SetBounds(758, 749, 120, 38);
            closeButton.Click += delegate { Close(); };
            Controls.Add(closeButton);

            progressBar = new ProgressBar();
            progressBar.SetBounds(22, 805, 650, 20);
            Controls.Add(progressBar);

            statusLabel = new Label();
            statusLabel.Text = "대기 중";
            statusLabel.TextAlign = ContentAlignment.MiddleRight;
            statusLabel.SetBounds(685, 802, 193, 25);
            Controls.Add(statusLabel);

            worker = new BackgroundWorker();
            worker.DoWork += WorkerDoWork;
            worker.RunWorkerCompleted += WorkerCompleted;

            DragEnter += FormDragEnter;
            DragDrop += FormDragDrop;
            FormClosing += MainFormClosing;
        }

        private void BrowseIso()
        {
            using (OpenFileDialog dialog = new OpenFileDialog())
            {
                dialog.Title = "복호화된 일본판 OG 문 드웰러즈 ISO 선택";
                dialog.Filter = "ISO 이미지 (*.iso)|*.iso|모든 파일 (*.*)|*.*";
                dialog.CheckFileExists = true;
                if (dialog.ShowDialog(this) == DialogResult.OK)
                {
                    isoPathBox.Text = dialog.FileName;
                    UpdateDefaultBackupPath();
                }
            }
        }

        private void BrowseBackup()
        {
            using (SaveFileDialog dialog = new SaveFileDialog())
            {
                dialog.Title = "원상복구 및 버전 갱신용 백업 파일 선택";
                dialog.Filter = "OGMD 복구 백업 (*.ogmd-backup)|*.ogmd-backup|모든 파일 (*.*)|*.*";
                dialog.AddExtension = false;
                dialog.OverwritePrompt = false;
                dialog.FileName = Path.GetFileName(backupPathBox.Text.Trim().Trim('"'));
                string directory = Path.GetDirectoryName(backupPathBox.Text.Trim().Trim('"'));
                if (!String.IsNullOrWhiteSpace(directory) && Directory.Exists(directory))
                    dialog.InitialDirectory = directory;
                if (dialog.ShowDialog(this) == DialogResult.OK)
                {
                    backupPathCustomized = true;
                    backupPathBox.Text = dialog.FileName;
                }
            }
        }

        private void BrowseRpcs3()
        {
            using (FolderBrowserDialog dialog = new FolderBrowserDialog())
            {
                dialog.Description = "rpcs3.exe가 있는 RPCS3 폴더를 선택하세요.";
                dialog.ShowNewFolderButton = false;
                string current = rpcs3PathBox.Text.Trim().Trim('"');
                if (!String.IsNullOrWhiteSpace(current) && Directory.Exists(current))
                    dialog.SelectedPath = current;
                if (dialog.ShowDialog(this) == DialogResult.OK)
                    rpcs3PathBox.Text = dialog.SelectedPath;
            }
        }

        private void UpdateDefaultBackupPath()
        {
            if (backupPathCustomized)
                return;
            string isoPath = isoPathBox.Text.Trim().Trim('"');
            backupPathBox.Text = String.IsNullOrWhiteSpace(isoPath) ? String.Empty : isoPath + ".ogmd-backup";
        }

        private void FormDragEnter(object sender, DragEventArgs e)
        {
            if (e.Data.GetDataPresent(DataFormats.FileDrop))
                e.Effect = DragDropEffects.Copy;
        }

        private void FormDragDrop(object sender, DragEventArgs e)
        {
            string[] files = e.Data.GetData(DataFormats.FileDrop) as string[];
            if (files != null && files.Length == 1 &&
                Path.GetExtension(files[0]).Equals(".iso", StringComparison.OrdinalIgnoreCase))
            {
                isoPathBox.Text = files[0];
                UpdateDefaultBackupPath();
            }
        }

        private void StartOperation(UiOperation operation)
        {
            string isoPath = isoPathBox.Text.Trim().Trim('"');
            if (!File.Exists(isoPath) || !Path.GetExtension(isoPath).Equals(".iso", StringComparison.OrdinalIgnoreCase))
            {
                MessageBox.Show(this, "유효한 ISO 파일을 선택하세요.", "ISO 확인", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            string backupPath = backupPathBox.Text.Trim().Trim('"');
            if (operation != UiOperation.Verify)
            {
                if (String.IsNullOrWhiteSpace(backupPath))
                {
                    MessageBox.Show(this, "복구 백업 파일의 저장 위치를 지정하세요.", "백업 경로 필요",
                        MessageBoxButtons.OK, MessageBoxIcon.Warning);
                    return;
                }
                backupPath = Path.GetFullPath(backupPath);
                if (String.Equals(Path.GetFullPath(isoPath), backupPath, StringComparison.OrdinalIgnoreCase))
                {
                    MessageBox.Show(this, "ISO 파일과 백업 파일은 서로 다른 경로여야 합니다.", "백업 경로 오류",
                        MessageBoxButtons.OK, MessageBoxIcon.Warning);
                    return;
                }
                string backupDirectory = Path.GetDirectoryName(backupPath);
                if (String.IsNullOrWhiteSpace(backupDirectory) || !Directory.Exists(backupDirectory))
                {
                    MessageBox.Show(this, "백업 파일을 저장할 폴더가 존재하지 않습니다.", "백업 경로 오류",
                        MessageBoxButtons.OK, MessageBoxIcon.Warning);
                    return;
                }
                if (operation == UiOperation.Restore && !File.Exists(backupPath))
                {
                    MessageBox.Show(this, "선택한 복구 백업 파일이 없습니다.", "백업 파일 확인",
                        MessageBoxButtons.OK, MessageBoxIcon.Warning);
                    return;
                }
            }

            if (operation != UiOperation.Verify && !warningCheck.Checked)
            {
                MessageBox.Show(this, "패치 또는 복구 전에 주의사항 확인란을 체크하세요.", "주의사항 확인 필요",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            bool deleteInstalledGame = operation == UiOperation.Patch && deleteInstalledGameCheck.Checked;
            string rpcs3Path = rpcs3PathBox.Text.Trim().Trim('"');
            if (deleteInstalledGame)
            {
                try
                {
                    rpcs3Path = ValidateRpcs3Root(rpcs3Path);
                }
                catch (Exception ex)
                {
                    MessageBox.Show(this, ex.Message, "RPCS3 경로 확인", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                    return;
                }
            }

            if (operation == UiOperation.Patch)
            {
                DialogResult answer = MessageBox.Show(this,
                    "선택한 ISO 파일 자체에 한국어 패치를 적용합니다.\r\n\r\n" +
                    "RPCS3가 완전히 종료되었고 ISO 마운트가 해제되었습니까?" +
                    (deleteInstalledGame ?
                        "\r\n\r\n패치 성공 후 다음 설치 폴더만 삭제합니다:\r\n" +
                        GetInstalledGamePath(rpcs3Path) : String.Empty),
                    "ISO 직접 패치 확인", MessageBoxButtons.YesNo, MessageBoxIcon.Warning, MessageBoxDefaultButton.Button2);
                if (answer != DialogResult.Yes)
                    return;
            }
            else if (operation == UiOperation.Restore)
            {
                DialogResult answer = MessageBox.Show(this,
                    "지정한 .ogmd-backup을 사용해 패치 전 원본 상태로 복구합니다. 계속하시겠습니까?",
                    "원본 복구 확인", MessageBoxButtons.YesNo, MessageBoxIcon.Question, MessageBoxDefaultButton.Button2);
                if (answer != DialogResult.Yes)
                    return;
            }

            logBox.Clear();
            SetBusy(true, operation == UiOperation.Verify ? "원본 검사 중..." :
                (operation == UiOperation.Patch ? "패치 적용 중..." : "원본 복구 중..."));
            worker.RunWorkerAsync(new object[]
            {
                operation, Path.GetFullPath(isoPath), backupPath, rpcs3Path, deleteInstalledGame
            });
        }

        private void WorkerDoWork(object sender, DoWorkEventArgs e)
        {
            object[] values = (object[])e.Argument;
            UiOperation operation = (UiOperation)values[0];
            string isoPath = (string)values[1];
            string backupPath = (string)values[2];
            string rpcs3Path = (string)values[3];
            bool deleteInstalledGame = (bool)values[4];
            UiResult result = new UiResult();
            result.Operation = operation;
            result.DeleteInstalledGame = deleteInstalledGame;
            result.Rpcs3Inspected = !String.IsNullOrWhiteSpace(rpcs3Path);

            TextWriter originalOutput = Console.Out;
            try
            {
                Console.SetOut(new UiTextWriter(AppendLog));
                Options options = new Options();
                options.IsoPath = isoPath;
                options.BackupPath = backupPath;
                options.Yes = true;
                options.VerifyOnly = operation == UiOperation.Verify;
                options.Restore = operation == UiOperation.Restore;
                options.Pause = false;
                options.Rpcs3Path = rpcs3Path;
                options.DeleteInstalledGame = deleteInstalledGame;
                result.ExitCode = Run(options);
            }
            catch (Exception ex)
            {
                result.ExitCode = 1;
                result.Error = ex;
                AppendLog(Environment.NewLine + "[실패] " + ex.Message + Environment.NewLine);
            }
            finally
            {
                Console.SetOut(originalOutput);
            }
            e.Result = result;
        }

        private void WorkerCompleted(object sender, RunWorkerCompletedEventArgs e)
        {
            SetBusy(false, "대기 중");
            UiResult result = e.Result as UiResult;
            if (result == null || result.Error != null || result.ExitCode != 0)
            {
                string message = result != null && result.Error != null ? result.Error.Message :
                    "검사 또는 작업이 성공적으로 끝나지 않았습니다. 진행 로그를 확인하세요.";
                MessageBox.Show(this, message, "작업 실패", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            if (result.Operation == UiOperation.Verify)
            {
                MessageBox.Show(this,
                    (result.Rpcs3Inspected ? "ISO와 RPCS3 경로 검사가 완료되었습니다." :
                        "ISO 검사가 완료되었습니다. RPCS3 경로는 입력되지 않아 검사하지 않았습니다.") +
                    "\r\n자세한 상태는 진행 로그를 확인하세요.",
                    "검사 완료", MessageBoxButtons.OK, MessageBoxIcon.Information);
            }
            else if (result.Operation == UiOperation.Patch)
            {
                MessageBox.Show(this,
                    "한국어 패치 적용과 최종 해시 검증이 완료되었습니다.\r\n\r\n" +
                    (result.DeleteInstalledGame ?
                        "선택한 RPCS3의 dev_hdd0\\game\\BLJS10335 설치 데이터 삭제도 완료했습니다.\r\n" :
                        "RPCS3 설치 데이터 삭제 옵션은 실행하지 않았습니다.\r\n") +
                    "세이브 데이터와 PPU/SPU/셰이더 캐시는 삭제하지 마세요.",
                    "패치 완료", MessageBoxButtons.OK, MessageBoxIcon.Information);
            }
            else
            {
                MessageBox.Show(this, "원본 ISO 복구와 해시 검증이 완료되었습니다.",
                    "복구 완료", MessageBoxButtons.OK, MessageBoxIcon.Information);
            }
        }

        private void AppendLog(string text)
        {
            if (IsDisposed)
                return;
            if (InvokeRequired)
            {
                try { BeginInvoke(new Action<string>(AppendLog), text); } catch { }
                return;
            }
            logBox.AppendText(text);
            logBox.SelectionStart = logBox.TextLength;
            logBox.ScrollToCaret();
        }

        private void MainFormClosing(object sender, FormClosingEventArgs e)
        {
            if (!busyState)
                return;
            e.Cancel = true;
            MessageBox.Show(this, "ISO 작업 중에는 창을 닫을 수 없습니다. 완료될 때까지 기다리세요.",
                "작업 진행 중", MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }

        private void SetBusy(bool busy, string status)
        {
            busyState = busy;
            isoPathBox.Enabled = !busy;
            browseButton.Enabled = !busy;
            backupPathBox.Enabled = !busy;
            backupBrowseButton.Enabled = !busy;
            rpcs3PathBox.Enabled = !busy;
            rpcs3BrowseButton.Enabled = !busy;
            deleteInstalledGameCheck.Enabled = !busy;
            warningCheck.Enabled = !busy;
            verifyButton.Enabled = !busy;
            patchButton.Enabled = !busy;
            restoreButton.Enabled = !busy;
            closeButton.Enabled = !busy;
            progressBar.Style = busy ? ProgressBarStyle.Marquee : ProgressBarStyle.Blocks;
            progressBar.MarqueeAnimationSpeed = busy ? 25 : 0;
            statusLabel.Text = status;
        }
    }

    [STAThread]
    private static int Main(string[] args)
    {
        bool commandLineMode = args.Any(delegate(string arg)
        {
            return arg.StartsWith("--", StringComparison.Ordinal);
        });

        if (!commandLineMode)
        {
            string initialIsoPath = args.Length > 0 ? args[0] : null;
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new MainForm(initialIsoPath));
            return 0;
        }

        InitializeConsoleForCli();

        bool pauseRequested = !args.Any(delegate(string arg)
        {
            return arg.Equals("--no-pause", StringComparison.OrdinalIgnoreCase) ||
                arg.Equals("--headless", StringComparison.OrdinalIgnoreCase);
        });
        Options options = null;
        int result = 1;
        try
        {
            Console.OutputEncoding = new UTF8Encoding(false);
            Console.Title = "OGMD 한국어 ISO 빠른 패처 " + VersionText;
            options = ParseOptions(args);
            result = Run(options);
        }
        catch (Exception ex)
        {
            SetConsoleColor(ConsoleColor.Red);
            Console.WriteLine();
            Console.WriteLine("[실패] " + ex.Message);
            ResetConsoleColor();
            result = 1;
        }
        finally
        {
            if ((options == null && pauseRequested) || (options != null && options.Pause))
            {
                Console.WriteLine();
                Console.Write("Enter 키를 누르면 종료합니다...");
                try { Console.ReadLine(); } catch { }
            }
        }
        return result;
    }

    private static void InitializeConsoleForCli()
    {
        try
        {
            AttachConsole(AttachParentProcess);

            Stream output = Console.OpenStandardOutput();
            if (output != null && output.CanWrite)
            {
                StreamWriter writer = new StreamWriter(output, new UTF8Encoding(false));
                writer.AutoFlush = true;
                Console.SetOut(writer);
            }

            Stream error = Console.OpenStandardError();
            if (error != null && error.CanWrite)
            {
                StreamWriter writer = new StreamWriter(error, new UTF8Encoding(false));
                writer.AutoFlush = true;
                Console.SetError(writer);
            }
        }
        catch
        {
            // GUI 실행에는 콘솔이 필요 없다. CLI에서 콘솔 연결에 실패해도 패치 로직은 계속 진행한다.
        }
    }

    private static Options ParseOptions(string[] args)
    {
        Options options = new Options();
        options.Pause = true;
        for (int index = 0; index < args.Length; index++)
        {
            string arg = args[index].Trim();
            if (arg.Equals("--yes", StringComparison.OrdinalIgnoreCase))
                options.Yes = true;
            else if (arg.Equals("--verify-only", StringComparison.OrdinalIgnoreCase))
                options.VerifyOnly = true;
            else if (arg.Equals("--restore", StringComparison.OrdinalIgnoreCase))
                options.Restore = true;
            else if (arg.Equals("--no-pause", StringComparison.OrdinalIgnoreCase))
                options.Pause = false;
            else if (arg.Equals("--headless", StringComparison.OrdinalIgnoreCase))
                options.Pause = false;
            else if (arg.Equals("--delete-installed-game", StringComparison.OrdinalIgnoreCase))
                options.DeleteInstalledGame = true;
            else if (arg.Equals("--backup", StringComparison.OrdinalIgnoreCase))
            {
                if (index + 1 >= args.Length)
                    throw new ArgumentException("--backup 다음에 백업 파일 경로를 지정하세요.");
                options.BackupPath = args[++index].Trim().Trim('"');
            }
            else if (arg.Equals("--rpcs3", StringComparison.OrdinalIgnoreCase))
            {
                if (index + 1 >= args.Length)
                    throw new ArgumentException("--rpcs3 다음에 rpcs3.exe가 있는 폴더 경로를 지정하세요.");
                options.Rpcs3Path = args[++index].Trim().Trim('"');
            }
            else if (arg.StartsWith("--", StringComparison.Ordinal))
                throw new ArgumentException("알 수 없는 옵션입니다: " + arg);
            else if (options.IsoPath == null)
                options.IsoPath = arg;
            else
                throw new ArgumentException("ISO 경로는 하나만 지정할 수 있습니다.");
        }

        if (String.IsNullOrWhiteSpace(options.IsoPath))
        {
            using (OpenFileDialog dialog = new OpenFileDialog())
            {
                dialog.Title = "복호화된 일본판 OG 문 드웰러즈 ISO 선택";
                dialog.Filter = "ISO 이미지 (*.iso)|*.iso|모든 파일 (*.*)|*.*";
                dialog.CheckFileExists = true;
                dialog.Multiselect = false;
                if (dialog.ShowDialog() != DialogResult.OK)
                    throw new OperationCanceledException("ISO 선택이 취소되었습니다.");
                options.IsoPath = dialog.FileName;
            }
        }

        if (options.DeleteInstalledGame && (options.VerifyOnly || options.Restore))
            throw new ArgumentException("--delete-installed-game은 패치 적용 작업에서만 사용할 수 있습니다.");

        options.IsoPath = Path.GetFullPath(options.IsoPath);
        if (!String.IsNullOrWhiteSpace(options.BackupPath))
            options.BackupPath = Path.GetFullPath(options.BackupPath);
        if (options.DeleteInstalledGame)
            options.Rpcs3Path = ValidateRpcs3Root(options.Rpcs3Path);
        else if (!String.IsNullOrWhiteSpace(options.Rpcs3Path))
            options.Rpcs3Path = Path.GetFullPath(options.Rpcs3Path);
        return options;
    }

    private static int Run(Options options)
    {
        WriteHeader();
        if (!File.Exists(options.IsoPath))
            throw new FileNotFoundException("ISO 파일이 없습니다.", options.IsoPath);
        if (!Path.GetExtension(options.IsoPath).Equals(".iso", StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("선택한 파일의 확장자가 .iso가 아닙니다.");
        if (Process.GetProcessesByName("rpcs3").Length != 0)
            throw new InvalidOperationException("RPCS3가 실행 중입니다. 완전히 종료한 뒤 다시 실행하세요.");

        Console.WriteLine("ISO: " + options.IsoPath);
        Console.WriteLine("방식: ISO 내부 변경 구간만 직접 기록 (전체 ISO 복사 없음)");
        Console.WriteLine();

        if (options.VerifyOnly)
            InspectRpcs3Path(options.Rpcs3Path);

        List<PackFile> patchFiles = LoadPack();
        string backupPath = String.IsNullOrWhiteSpace(options.BackupPath) ?
            options.IsoPath + ".ogmd-backup" : Path.GetFullPath(options.BackupPath);
        if (String.Equals(options.IsoPath, backupPath, StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("ISO 파일과 백업 파일은 서로 다른 경로여야 합니다.");
        string backupDirectory = Path.GetDirectoryName(backupPath);
        if (String.IsNullOrWhiteSpace(backupDirectory) || !Directory.Exists(backupDirectory))
            throw new DirectoryNotFoundException("백업 파일을 저장할 폴더가 없습니다: " + backupDirectory);
        Console.WriteLine("백업: " + backupPath);
        Console.WriteLine();

        using (FileStream iso = new FileStream(
            options.IsoPath, FileMode.Open, options.VerifyOnly ? FileAccess.Read : FileAccess.ReadWrite,
            FileShare.None, 4 * 1024 * 1024, FileOptions.RandomAccess))
        {
            List<LocatedFile> located = LocateFiles(iso, patchFiles);
            List<PhysicalSegment> segments = BuildSegments(located);
            Dictionary<LocatedFile, FileState> states;
            string fastCheckDetail;
            if (TryVerifyStatesFast(iso, located, segments, backupPath, out states, out fastCheckDetail))
            {
                WriteOk("기존 백업을 이용한 빠른 ISO 검사 완료: " + fastCheckDetail);
            }
            else
            {
                if (File.Exists(backupPath))
                    Console.WriteLine("[*] 빠른 검사 미사용: " + fastCheckDetail);
                Console.WriteLine("[*] PSARC 전체 해시 검사로 전환합니다.");
                states = VerifyStates(iso, located);
            }

            if (options.VerifyOnly)
            {
                PrintOverallState(states);
                return states.Values.All(delegate(FileState state) { return state != FileState.Unknown; }) ? 0 : 2;
            }

            if (options.Restore)
                return RestoreMode(iso, located, states, backupPath, options.Yes);

            if (states.Values.All(delegate(FileState state) { return state == FileState.Target; }))
            {
                WriteOk("이미 이 버전의 한국어 패치가 적용된 ISO입니다.");
                if (File.Exists(backupPath))
                {
                    Console.WriteLine("복구 백업: " + backupPath);
                    if (!options.Yes && AskYes("한국어 패치를 제거하고 원본으로 복구하시겠습니까? [Y/N]: "))
                        return RestoreMode(iso, located, states, backupPath, true);
                }
                DeleteInstalledGameIfRequested(options);
                return 0;
            }

            if (states.Values.Any(delegate(FileState state) { return state == FileState.Unknown; }) ||
                states.Values.Any(delegate(FileState state) { return state == FileState.Target; }))
            {
                if (!File.Exists(backupPath))
                    throw new InvalidDataException(
                        "ISO가 현재 버전의 원본도 완성본도 아니며 지정한 복구 백업도 없습니다. " +
                        "이전 패치 버전이라면 당시 생성한 백업 파일을 선택하세요.");

                SetConsoleColor(ConsoleColor.Yellow);
                Console.WriteLine("[!] 이전 패치 버전 또는 중단 상태를 감지했습니다.");
                Console.WriteLine("    지정한 백업으로 원본 상태를 복원한 뒤 현재 버전을 적용합니다.");
                ResetConsoleColor();
                Confirm(options.Yes, "복구 후 패치를 다시 적용하시겠습니까? [Y/N]: ");
                RestoreBackup(iso, backupPath);
                states = VerifyStates(iso, located);
                if (!states.Values.All(delegate(FileState state) { return state == FileState.Source; }))
                    throw new InvalidDataException("백업 복구 후에도 원본 해시가 일치하지 않습니다. ISO를 확인하세요.");
                WriteOk("중단 상태 복구 완료");
            }

            if (!states.Values.All(delegate(FileState state) { return state == FileState.Source; }))
                throw new InvalidDataException("지원되는 일본판 원본 ISO가 아닙니다.");

            SetConsoleColor(ConsoleColor.Yellow);
            Console.WriteLine("주의: 이 작업은 선택한 ISO 파일 자체를 수정합니다.");
            Console.WriteLine("원상복구 및 다음 버전 갱신용 백업은 지정한 경로에 보존됩니다.");
            ResetConsoleColor();
            Confirm(options.Yes, "계속하시겠습니까? [Y/N]: ");

            Console.WriteLine("기록 구간: {0:N0}개 / 실제 데이터 {1:N0} bytes", segments.Count,
                segments.Sum(delegate(PhysicalSegment segment) { return (long)segment.Length; }));

            bool refreshingBackup = File.Exists(backupPath);
            CreateBackup(iso, backupPath, segments);
            WriteOk((refreshingBackup ? "기존 복구 백업 갱신 완료: " : "원상복구 백업 생성 완료: ") + backupPath);

            try
            {
                ApplySegments(iso, segments);
                states = VerifyStates(iso, located);
                if (!states.Values.All(delegate(FileState state) { return state == FileState.Target; }))
                    throw new InvalidDataException("패치 후 최종 해시가 일치하지 않습니다.");
            }
            catch
            {
                SetConsoleColor(ConsoleColor.Yellow);
                Console.WriteLine("[!] 적용 실패. 백업으로 ISO를 자동 복구합니다.");
                ResetConsoleColor();
                RestoreBackup(iso, backupPath);
                states = VerifyStates(iso, located);
                if (!states.Values.All(delegate(FileState state) { return state == FileState.Source; }))
                    throw new InvalidDataException(
                        "자동 복구 검증에 실패했습니다. 백업 파일을 삭제하지 말고 --restore로 다시 복구하세요.");
                WriteOk("원본 ISO 자동 복구 완료");
                throw;
            }

            Console.WriteLine();
            WriteOk("ISO 직접 패치 및 최종 해시 검증 4/4 완료");
            Console.WriteLine("복구하려면 이 실행 파일을 다음 옵션으로 실행하세요:");
            Console.WriteLine("  OGMD_ISO_QuickPatch.exe --restore --backup \"" + backupPath + "\" \"" + options.IsoPath + "\"");
            Console.WriteLine("복구 백업은 삭제하지 않는 것을 권장합니다:");
            Console.WriteLine("  " + backupPath);
            DeleteInstalledGameIfRequested(options);
            return 0;
        }
    }

    private static string ValidateRpcs3Root(string path)
    {
        if (String.IsNullOrWhiteSpace(path))
            throw new ArgumentException("설치 데이터를 삭제하려면 RPCS3 폴더를 지정하세요.");

        string root = Path.GetFullPath(path.Trim().Trim('"'))
            .TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        if (!Directory.Exists(root))
            throw new DirectoryNotFoundException("RPCS3 폴더가 없습니다: " + root);
        if (!File.Exists(Path.Combine(root, "rpcs3.exe")))
            throw new FileNotFoundException("선택한 폴더에서 rpcs3.exe를 찾을 수 없습니다.",
                Path.Combine(root, "rpcs3.exe"));

        GetInstalledGamePath(root);
        return root;
    }

    private static void InspectRpcs3Path(string path)
    {
        Console.WriteLine("[RPCS3 경로 검사]");
        if (String.IsNullOrWhiteSpace(path))
        {
            SetConsoleColor(ConsoleColor.Yellow);
            Console.WriteLine("[!] RPCS3 경로가 입력되지 않아 ISO만 검사합니다.");
            ResetConsoleColor();
            Console.WriteLine();
            return;
        }

        string root = ValidateRpcs3Root(path);
        string devHdd0 = Path.Combine(root, "dev_hdd0");
        string gameRoot = Path.Combine(devHdd0, "game");
        string install = GetInstalledGamePath(root);

        WriteOk("RPCS3 실행 파일 확인: " + Path.Combine(root, "rpcs3.exe"));
        if (!Directory.Exists(devHdd0))
            throw new DirectoryNotFoundException("선택한 RPCS3 폴더에 dev_hdd0가 없습니다: " + devHdd0);
        WriteOk("dev_hdd0 확인: " + devHdd0);

        if (!Directory.Exists(gameRoot))
            throw new DirectoryNotFoundException("선택한 RPCS3 폴더에 dev_hdd0\\game이 없습니다: " + gameRoot);
        WriteOk("게임 설치 루트 확인: " + gameRoot);

        if (Directory.Exists(install))
        {
            SetConsoleColor(ConsoleColor.Yellow);
            Console.WriteLine("[!] 기존 OGMD 설치 데이터가 있습니다: " + install);
            Console.WriteLine("    새 ISO 패치 내용을 사용하려면 패치 적용 시 설치 데이터 삭제 옵션을 선택하세요.");
            ResetConsoleColor();
        }
        else
        {
            WriteOk("활성 OGMD 설치 데이터 없음: " + install);
        }

        int preservedCount = 0;
        try
        {
            preservedCount = Directory.GetDirectories(gameRoot, "BLJS10335.pre_*", SearchOption.TopDirectoryOnly).Length;
        }
        catch (Exception ex)
        {
            throw new IOException("보존 설치 폴더 상태를 확인하지 못했습니다: " + gameRoot, ex);
        }
        Console.WriteLine("보존 폴더 BLJS10335.pre_*: {0}개", preservedCount);
        Console.WriteLine("세이브·savestate·PPU/SPU/셰이더 캐시는 검사 과정에서 변경하지 않습니다.");
        Console.WriteLine();
    }

    private static string GetInstalledGamePath(string rpcs3Root)
    {
        string root = Path.GetFullPath(rpcs3Root)
            .TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        string gameParent = Path.GetFullPath(Path.Combine(root, "dev_hdd0", "game"));
        string target = Path.GetFullPath(Path.Combine(gameParent, "BLJS10335"));
        string expected = gameParent.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar) +
            Path.DirectorySeparatorChar + "BLJS10335";
        if (!String.Equals(target, expected, StringComparison.OrdinalIgnoreCase) ||
            !String.Equals(Path.GetFileName(target), "BLJS10335", StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("안전 검증에 실패해 설치 데이터 삭제를 중단했습니다.");
        return target;
    }

    private static void DeleteInstalledGameIfRequested(Options options)
    {
        if (!options.DeleteInstalledGame)
            return;
        if (options.VerifyOnly || options.Restore)
            throw new InvalidOperationException("설치 데이터 삭제는 한국어 패치 적용 작업에서만 사용할 수 있습니다.");

        string root = ValidateRpcs3Root(options.Rpcs3Path);
        string target = GetInstalledGamePath(root);
        if (!Directory.Exists(target))
        {
            WriteOk("삭제할 기존 설치 데이터가 없습니다: " + target);
            return;
        }

        FileAttributes attributes = File.GetAttributes(target);
        if ((attributes & FileAttributes.ReparsePoint) != 0)
            throw new InvalidDataException("설치 폴더가 링크 또는 재분석 지점이어서 삭제하지 않았습니다: " + target);

        Directory.Delete(target, true);
        if (Directory.Exists(target))
            throw new IOException("기존 설치 데이터 폴더 삭제에 실패했습니다: " + target);
        WriteOk("RPCS3 기존 설치 데이터 삭제 완료: " + target);
        Console.WriteLine("세이브·savestate·PPU/SPU/셰이더 캐시와 BLJS10335.pre_* 폴더는 건드리지 않았습니다.");
    }

    private static int RestoreMode(
        FileStream iso, List<LocatedFile> located, Dictionary<LocatedFile, FileState> states,
        string backupPath, bool automaticYes)
    {
        if (states.Values.All(delegate(FileState state) { return state == FileState.Source; }))
        {
            WriteOk("이미 일본판 원본 상태입니다.");
            return 0;
        }
        if (!File.Exists(backupPath))
            throw new FileNotFoundException("복구 백업이 없습니다.", backupPath);

        Confirm(automaticYes, "한국어 패치를 제거하고 원본으로 복구하시겠습니까? [Y/N]: ");
        RestoreBackup(iso, backupPath);
        Dictionary<LocatedFile, FileState> after = VerifyStates(iso, located);
        if (!after.Values.All(delegate(FileState state) { return state == FileState.Source; }))
            throw new InvalidDataException("복구 후 원본 해시 검증에 실패했습니다. 백업을 삭제하지 마세요.");
        WriteOk("원본 ISO 복구 및 해시 검증 4/4 완료");
        Console.WriteLine("백업은 재적용에 대비해 그대로 보존했습니다: " + backupPath);
        return 0;
    }

    private static void Confirm(bool automaticYes, string message)
    {
        if (automaticYes)
            return;
        if (!AskYes(message))
            throw new OperationCanceledException("사용자가 작업을 취소했습니다.");
    }

    private static bool AskYes(string message)
    {
        Console.Write(message);
        string answer = Console.ReadLine();
        return String.Equals(answer, "Y", StringComparison.OrdinalIgnoreCase);
    }

    private static void SetConsoleColor(ConsoleColor color)
    {
        try { Console.ForegroundColor = color; } catch { }
    }

    private static void ResetConsoleColor()
    {
        try { Console.ResetColor(); } catch { }
    }

    private static void WriteHeader()
    {
        SetConsoleColor(ConsoleColor.Cyan);
        Console.WriteLine("============================================================");
        Console.WriteLine(" OGMD 한국어 ISO 빠른 패처 " + VersionText);
        Console.WriteLine("============================================================");
        ResetConsoleColor();
    }

    private static void WriteOk(string message)
    {
        SetConsoleColor(ConsoleColor.Green);
        Console.WriteLine("[OK] " + message);
        ResetConsoleColor();
    }

    private static List<PackFile> LoadPack()
    {
        Stream resource = Assembly.GetExecutingAssembly().GetManifestResourceStream(PatchResourceName);
        if (resource == null)
            throw new InvalidDataException("실행 파일 내부 패치 데이터를 찾을 수 없습니다.");

        using (resource)
        using (BinaryReader reader = new BinaryReader(resource, Encoding.UTF8))
        {
            string magic = Encoding.ASCII.GetString(ReadExactly(reader, 8));
            if (magic != PackMagic)
                throw new InvalidDataException("패치 데이터 형식이 올바르지 않습니다.");
            int version = reader.ReadInt32();
            int fileCount = reader.ReadInt32();
            if (version != FormatVersion || fileCount != 4)
                throw new InvalidDataException("지원하지 않는 패치 데이터 버전입니다.");

            List<PackFile> files = new List<PackFile>();
            for (int fileIndex = 0; fileIndex < fileCount; fileIndex++)
            {
                PackFile file = new PackFile();
                int pathLength = reader.ReadUInt16();
                file.IsoPath = Encoding.UTF8.GetString(ReadExactly(reader, pathLength));
                file.Size = checked((long)reader.ReadUInt64());
                file.SourceHash = ReadExactly(reader, 32);
                file.TargetHash = ReadExactly(reader, 32);
                int rangeCount = checked((int)reader.ReadUInt32());
                for (int rangeIndex = 0; rangeIndex < rangeCount; rangeIndex++)
                {
                    long offset = checked((long)reader.ReadUInt64());
                    int length = checked((int)reader.ReadUInt32());
                    if (offset < 0 || length <= 0 || offset + length > file.Size)
                        throw new InvalidDataException("패치 구간이 파일 범위를 벗어났습니다: " + file.IsoPath);
                    file.Ranges.Add(new PatchRange { LogicalOffset = offset, Data = ReadExactly(reader, length) });
                }
                files.Add(file);
            }
            if (resource.Position != resource.Length)
                throw new InvalidDataException("패치 데이터 끝에 알 수 없는 데이터가 있습니다.");
            return files;
        }
    }

    private static byte[] ReadExactly(BinaryReader reader, int count)
    {
        byte[] data = reader.ReadBytes(count);
        if (data.Length != count)
            throw new EndOfStreamException("패치 데이터를 읽는 중 파일 끝에 도달했습니다.");
        return data;
    }

    private static List<LocatedFile> LocateFiles(FileStream iso, List<PackFile> patchFiles)
    {
        Console.WriteLine("[*] ISO9660 구조 확인");
        IsoRecord root = FindRoot(iso);
        List<LocatedFile> result = new List<LocatedFile>();
        foreach (PackFile patch in patchFiles)
        {
            List<IsoRecord> records = FindIsoPath(iso, root, patch.IsoPath)
                .Where(delegate(IsoRecord record) { return !record.IsDirectory; }).ToList();
            if (records.Count == 0)
                throw new InvalidDataException("ISO 내부 파일을 찾을 수 없습니다: " + patch.IsoPath);

            LocatedFile located = new LocatedFile { Patch = patch };
            foreach (IsoRecord record in records)
            {
                if (record.FileUnitSize != 0 || record.InterleaveGap != 0)
                    throw new InvalidDataException("인터리브 ISO 파일은 지원하지 않습니다: " + patch.IsoPath);
                located.Extents.Add(new IsoExtent
                {
                    Offset = checked((long)record.Extent * SectorSize),
                    Size = record.Size,
                    Lba = record.Extent
                });
            }
            long total = located.Extents.Sum(delegate(IsoExtent extent) { return extent.Size; });
            if (total != patch.Size)
                throw new InvalidDataException("ISO 내부 파일 크기가 다릅니다: " + patch.IsoPath);
            if (located.Extents.Any(delegate(IsoExtent extent) { return extent.Offset + extent.Size > iso.Length; }))
                throw new InvalidDataException("ISO extent가 이미지 범위를 벗어났습니다: " + patch.IsoPath);
            result.Add(located);
            Console.WriteLine("    {0,-10} {1:N0} bytes / extent {2}",
                Path.GetFileNameWithoutExtension(Path.GetFileNameWithoutExtension(patch.IsoPath)),
                patch.Size, located.Extents.Count);
        }
        return result;
    }

    private static IsoRecord FindRoot(FileStream iso)
    {
        byte[] descriptor = new byte[SectorSize];
        for (int sector = 16; sector < 64; sector++)
        {
            iso.Position = (long)sector * SectorSize;
            ReadFully(iso, descriptor, 0, descriptor.Length);
            if (Encoding.ASCII.GetString(descriptor, 1, 5) != "CD001")
                continue;
            if (descriptor[0] == 1)
            {
                IsoRecord root = ParseIsoRecord(descriptor, 156);
                if (root == null || !root.IsDirectory)
                    throw new InvalidDataException("ISO 루트 디렉터리를 읽을 수 없습니다.");
                return root;
            }
            if (descriptor[0] == 255)
                break;
        }
        throw new InvalidDataException(
            "표준 ISO9660을 찾을 수 없습니다. 암호화된 PS3 ISO는 먼저 복호화해야 합니다.");
    }

    private static List<IsoRecord> FindIsoPath(FileStream iso, IsoRecord root, string path)
    {
        string[] parts = path.Split(new[] { '/', '\\' }, StringSplitOptions.RemoveEmptyEntries);
        IsoRecord current = root;
        for (int index = 0; index < parts.Length; index++)
        {
            List<IsoRecord> matches = ReadDirectory(iso, current)
                .Where(delegate(IsoRecord record)
                {
                    return record.Name.Equals(parts[index], StringComparison.OrdinalIgnoreCase);
                }).ToList();
            if (matches.Count == 0)
                throw new InvalidDataException("ISO 내부 경로가 없습니다: " + path + " (" + parts[index] + ")");
            if (index == parts.Length - 1)
                return matches;
            current = matches[0];
            if (!current.IsDirectory)
                throw new InvalidDataException("ISO 경로 중간 항목이 디렉터리가 아닙니다: " + parts[index]);
        }
        return new List<IsoRecord> { current };
    }

    private static List<IsoRecord> ReadDirectory(FileStream iso, IsoRecord directory)
    {
        if (!directory.IsDirectory || directory.Size > Int32.MaxValue)
            throw new InvalidDataException("지원하지 않는 ISO 디렉터리입니다.");
        byte[] data = new byte[(int)directory.Size];
        iso.Position = checked((long)directory.Extent * SectorSize);
        ReadFully(iso, data, 0, data.Length);

        List<IsoRecord> records = new List<IsoRecord>();
        int position = 0;
        while (position < data.Length)
        {
            int length = data[position];
            if (length == 0)
            {
                position = ((position / SectorSize) + 1) * SectorSize;
                continue;
            }
            IsoRecord record = ParseIsoRecord(data, position);
            if (record != null && record.Name != "." && record.Name != "..")
                records.Add(record);
            position += length;
        }
        return records;
    }

    private static IsoRecord ParseIsoRecord(byte[] data, int offset)
    {
        int length = data[offset];
        if (length == 0)
            return null;
        if (offset < 0 || offset + length > data.Length || length < 34)
            throw new InvalidDataException("손상된 ISO 디렉터리 레코드입니다.");

        int nameLength = data[offset + 32];
        if (offset + 33 + nameLength > data.Length)
            throw new InvalidDataException("손상된 ISO 파일명 레코드입니다.");
        string name;
        if (nameLength == 1 && data[offset + 33] == 0)
            name = ".";
        else if (nameLength == 1 && data[offset + 33] == 1)
            name = "..";
        else
        {
            name = Encoding.ASCII.GetString(data, offset + 33, nameLength);
            int semicolon = name.IndexOf(';');
            if (semicolon >= 0)
                name = name.Substring(0, semicolon);
        }

        int flags = data[offset + 25];
        return new IsoRecord
        {
            Name = name,
            Extent = BitConverter.ToUInt32(data, offset + 2),
            Size = BitConverter.ToUInt32(data, offset + 10),
            IsDirectory = (flags & 2) != 0,
            IsMultiExtent = (flags & 128) != 0,
            FileUnitSize = data[offset + 26],
            InterleaveGap = data[offset + 27]
        };
    }

    private static Dictionary<LocatedFile, FileState> VerifyStates(FileStream iso, List<LocatedFile> files)
    {
        Console.WriteLine("[*] ISO 내부 PSARC SHA-256 검증");
        Dictionary<LocatedFile, FileState> states = new Dictionary<LocatedFile, FileState>();
        foreach (LocatedFile file in files)
        {
            byte[] hash = HashExtents(iso, file.Extents);
            FileState state = EqualBytes(hash, file.Patch.SourceHash) ? FileState.Source :
                (EqualBytes(hash, file.Patch.TargetHash) ? FileState.Target : FileState.Unknown);
            states.Add(file, state);
            Console.WriteLine("    {0,-10} {1}  {2}",
                Path.GetFileNameWithoutExtension(Path.GetFileNameWithoutExtension(file.Patch.IsoPath)),
                ToHex(hash), state == FileState.Source ? "원본" :
                (state == FileState.Target ? "패치됨" : "불일치"));
        }
        return states;
    }

    private static void PrintOverallState(Dictionary<LocatedFile, FileState> states)
    {
        if (states.Values.All(delegate(FileState state) { return state == FileState.Source; }))
            WriteOk("지원되는 일본판 원본 ISO입니다. 빠른 패치를 적용할 수 있습니다.");
        else if (states.Values.All(delegate(FileState state) { return state == FileState.Target; }))
            WriteOk("한국어 패치가 정상 적용된 ISO입니다.");
        else
        {
            SetConsoleColor(ConsoleColor.Red);
            Console.WriteLine("[불일치] 지원되지 않거나 중간 상태인 ISO입니다.");
            ResetConsoleColor();
        }
    }

    private static byte[] HashExtents(FileStream iso, List<IsoExtent> extents)
    {
        using (SHA256 sha = SHA256.Create())
        {
            byte[] buffer = new byte[4 * 1024 * 1024];
            foreach (IsoExtent extent in extents)
            {
                iso.Position = extent.Offset;
                long remaining = extent.Size;
                while (remaining > 0)
                {
                    int wanted = (int)Math.Min((long)buffer.Length, remaining);
                    int read = iso.Read(buffer, 0, wanted);
                    if (read <= 0)
                        throw new EndOfStreamException("ISO 해시 계산 중 파일 끝에 도달했습니다.");
                    sha.TransformBlock(buffer, 0, read, buffer, 0);
                    remaining -= read;
                }
            }
            sha.TransformFinalBlock(new byte[0], 0, 0);
            return sha.Hash;
        }
    }

    private static List<PhysicalSegment> BuildSegments(List<LocatedFile> files)
    {
        List<PhysicalSegment> segments = new List<PhysicalSegment>();
        foreach (LocatedFile file in files)
        {
            foreach (PatchRange range in file.Patch.Ranges)
            {
                long logical = range.LogicalOffset;
                int dataOffset = 0;
                int remaining = range.Data.Length;
                long extentLogicalStart = 0;
                foreach (IsoExtent extent in file.Extents)
                {
                    long extentLogicalEnd = extentLogicalStart + extent.Size;
                    if (logical >= extentLogicalEnd)
                    {
                        extentLogicalStart = extentLogicalEnd;
                        continue;
                    }
                    if (logical < extentLogicalStart)
                        throw new InvalidDataException("패치 구간 extent 변환에 실패했습니다.");
                    long inside = logical - extentLogicalStart;
                    int count = (int)Math.Min((long)remaining, extent.Size - inside);
                    segments.Add(new PhysicalSegment
                    {
                        AbsoluteOffset = extent.Offset + inside,
                        Data = range.Data,
                        DataOffset = dataOffset,
                        Length = count
                    });
                    logical += count;
                    dataOffset += count;
                    remaining -= count;
                    if (remaining == 0)
                        break;
                    extentLogicalStart = extentLogicalEnd;
                }
                if (remaining != 0)
                    throw new InvalidDataException("패치 구간이 ISO extent 범위를 벗어났습니다.");
            }
        }
        segments.Sort(delegate(PhysicalSegment left, PhysicalSegment right)
        {
            return left.AbsoluteOffset.CompareTo(right.AbsoluteOffset);
        });
        for (int index = 1; index < segments.Count; index++)
        {
            PhysicalSegment previous = segments[index - 1];
            if (previous.AbsoluteOffset + previous.Length > segments[index].AbsoluteOffset)
                throw new InvalidDataException("겹치는 물리 패치 구간이 발견되었습니다.");
        }
        return segments;
    }

    private static bool TryVerifyStatesFast(
        FileStream iso, List<LocatedFile> located, List<PhysicalSegment> expectedSegments,
        string backupPath, out Dictionary<LocatedFile, FileState> states, out string detail)
    {
        states = null;
        detail = "기존 백업이 없습니다.";
        if (!File.Exists(backupPath))
            return false;

        List<PhysicalSegment> originals;
        int backupVersion;
        try
        {
            originals = ReadBackupSegments(backupPath, iso.Length, true, out backupVersion);
        }
        catch (Exception ex)
        {
            detail = ex.Message;
            return false;
        }

        if (originals.Count != expectedSegments.Count)
        {
            detail = "백업 구간 수가 현재 패치와 다릅니다.";
            return false;
        }

        bool allSource = true;
        bool allTarget = true;
        byte[] current = null;
        for (int index = 0; index < expectedSegments.Count; index++)
        {
            PhysicalSegment expected = expectedSegments[index];
            PhysicalSegment original = originals[index];
            if (original.AbsoluteOffset != expected.AbsoluteOffset || original.Length != expected.Length)
            {
                detail = "백업 구간 배치가 현재 패치와 다릅니다.";
                return false;
            }

            if (current == null || current.Length < expected.Length)
                current = new byte[expected.Length];
            iso.Position = expected.AbsoluteOffset;
            ReadFully(iso, current, 0, expected.Length);

            bool sourceMatch = BytesEqual(current, 0, original.Data, original.DataOffset, expected.Length);
            bool targetMatch = BytesEqual(current, 0, expected.Data, expected.DataOffset, expected.Length);
            allSource = allSource && sourceMatch;
            allTarget = allTarget && targetMatch;
            if (!allSource && !allTarget)
            {
                detail = "변경 구간 상태가 원본이나 현재 패치와 완전히 일치하지 않습니다.";
                return false;
            }
        }

        FileState state;
        if (allSource && !allTarget)
            state = FileState.Source;
        else if (allTarget && !allSource)
            state = FileState.Target;
        else
        {
            detail = "변경 구간만으로 ISO 상태를 구분할 수 없습니다.";
            return false;
        }

        states = located.ToDictionary(
            delegate(LocatedFile item) { return item; },
            delegate(LocatedFile item) { return state; });
        detail = state == FileState.Source ? "일본판 원본 상태" : "현재 한국어 패치 상태";
        return true;
    }

    private static bool BytesEqual(
        byte[] left, int leftOffset, byte[] right, int rightOffset, int count)
    {
        if (left == null || right == null || leftOffset < 0 || rightOffset < 0 || count < 0 ||
            leftOffset + count > left.Length || rightOffset + count > right.Length)
            return false;
        for (int index = 0; index < count; index++)
        {
            if (left[leftOffset + index] != right[rightOffset + index])
                return false;
        }
        return true;
    }

    private static List<PhysicalSegment> ReadBackupSegments(
        string backupPath, long expectedIsoLength, bool requireFastFormat, out int version)
    {
        using (FileStream input = new FileStream(
            backupPath, FileMode.Open, FileAccess.Read, FileShare.Read, 1024 * 1024, FileOptions.SequentialScan))
        using (BinaryReader reader = new BinaryReader(input, Encoding.UTF8))
        {
            string magic = Encoding.ASCII.GetString(ReadExactly(reader, 8));
            version = reader.ReadInt32();
            long storedIsoLength = reader.ReadInt64();
            int count = reader.ReadInt32();
            if (magic != BackupMagic ||
                (version != LegacyBackupFormatVersion && version != BackupFormatVersion) ||
                storedIsoLength != expectedIsoLength || count < 1 || count > 2000000)
                throw new InvalidDataException("복구 백업이 현재 ISO와 맞지 않습니다.");
            if (requireFastFormat && version != BackupFormatVersion)
                throw new InvalidDataException("구형 백업이어서 빠른 검사를 지원하지 않습니다.");

            List<PhysicalSegment> result = new List<PhysicalSegment>(count);
            long previousEnd = -1;
            for (int index = 0; index < count; index++)
            {
                long offset = reader.ReadInt64();
                int length = reader.ReadInt32();
                if (offset < 0 || length <= 0 || offset + length > expectedIsoLength ||
                    length > 64 * 1024 * 1024 || offset < previousEnd)
                    throw new InvalidDataException("복구 백업 구간이 올바르지 않습니다.");
                byte[] original = ReadExactly(reader, length);
                result.Add(new PhysicalSegment
                {
                    AbsoluteOffset = offset,
                    Data = original,
                    DataOffset = 0,
                    Length = length
                });
                previousEnd = offset + length;
            }

            if (version == BackupFormatVersion)
            {
                if (input.Length - input.Position != BackupFooterHashSize)
                    throw new InvalidDataException("복구 백업 무결성 정보가 올바르지 않습니다.");
                byte[] storedHash = ReadExactly(reader, BackupFooterHashSize);
                input.Position = 0;
                byte[] actualHash = ComputeHashPrefix(input, input.Length - BackupFooterHashSize);
                if (!BytesEqual(storedHash, 0, actualHash, 0, BackupFooterHashSize))
                    throw new InvalidDataException("복구 백업 무결성 검사에 실패했습니다.");
            }
            else if (input.Position != input.Length)
            {
                throw new InvalidDataException("복구 백업 끝에 알 수 없는 데이터가 있습니다.");
            }
            return result;
        }
    }

    private static byte[] ComputeHashPrefix(Stream input, long length)
    {
        if (length < 0 || length > input.Length)
            throw new ArgumentOutOfRangeException("length");
        input.Position = 0;
        using (SHA256 sha = SHA256.Create())
        {
            byte[] buffer = new byte[1024 * 1024];
            long remaining = length;
            while (remaining > 0)
            {
                int request = (int)Math.Min(buffer.Length, remaining);
                int read = input.Read(buffer, 0, request);
                if (read <= 0)
                    throw new EndOfStreamException("백업 무결성을 검사하는 중 파일 끝에 도달했습니다.");
                sha.TransformBlock(buffer, 0, read, null, 0);
                remaining -= read;
            }
            sha.TransformFinalBlock(new byte[0], 0, 0);
            return sha.Hash;
        }
    }

    private static void CreateBackup(FileStream iso, string backupPath, List<PhysicalSegment> segments)
    {
        string temporary = backupPath + ".tmp";
        if (File.Exists(temporary))
            File.Delete(temporary);

        using (MemoryMappedFile map = MemoryMappedFile.CreateFromFile(
            iso, null, 0, MemoryMappedFileAccess.Read, null, HandleInheritability.None, true))
        using (MemoryMappedViewAccessor view = map.CreateViewAccessor(0, 0, MemoryMappedFileAccess.Read))
        using (FileStream output = new FileStream(
            temporary, FileMode.CreateNew, FileAccess.Write, FileShare.None, 1024 * 1024, FileOptions.SequentialScan))
        using (BinaryWriter writer = new BinaryWriter(output, Encoding.UTF8))
        {
            writer.Write(Encoding.ASCII.GetBytes(BackupMagic));
            writer.Write(BackupFormatVersion);
            writer.Write(iso.Length);
            writer.Write(segments.Count);
            foreach (PhysicalSegment segment in segments)
            {
                byte[] original = new byte[segment.Length];
                view.ReadArray(segment.AbsoluteOffset, original, 0, original.Length);
                writer.Write(segment.AbsoluteOffset);
                writer.Write(original.Length);
                writer.Write(original);
            }
            writer.Flush();
            output.Flush(true);
        }

        byte[] integrityHash;
        using (FileStream input = new FileStream(
            temporary, FileMode.Open, FileAccess.Read, FileShare.Read, 1024 * 1024, FileOptions.SequentialScan))
        using (SHA256 sha = SHA256.Create())
        {
            integrityHash = sha.ComputeHash(input);
        }
        using (FileStream output = new FileStream(
            temporary, FileMode.Append, FileAccess.Write, FileShare.None, 4096, FileOptions.WriteThrough))
        {
            output.Write(integrityHash, 0, integrityHash.Length);
            output.Flush(true);
        }

        if (File.Exists(backupPath))
            File.Delete(backupPath);
        File.Move(temporary, backupPath);
    }

    private static void ApplySegments(FileStream iso, List<PhysicalSegment> segments)
    {
        Console.WriteLine("[*] ISO 변경 구간 직접 기록");
        using (MemoryMappedFile map = MemoryMappedFile.CreateFromFile(
            iso, null, 0, MemoryMappedFileAccess.ReadWrite, null, HandleInheritability.None, true))
        using (MemoryMappedViewAccessor view = map.CreateViewAccessor(0, 0, MemoryMappedFileAccess.ReadWrite))
        {
            int done = 0;
            int nextPercent = 10;
            foreach (PhysicalSegment segment in segments)
            {
                view.WriteArray(segment.AbsoluteOffset, segment.Data, segment.DataOffset, segment.Length);
                done++;
                int percent = (int)((done * 100L) / segments.Count);
                if (percent >= nextPercent)
                {
                    Console.WriteLine("    {0}%", percent);
                    nextPercent += 10;
                }
            }
            view.Flush();
        }
        iso.Flush(true);
        WriteOk("변경 구간 기록 완료");
    }

    private static void RestoreBackup(FileStream iso, string backupPath)
    {
        Console.WriteLine("[*] 원상복구 백업 적용");
        int backupVersion;
        List<PhysicalSegment> backupSegments = ReadBackupSegments(
            backupPath, iso.Length, false, out backupVersion);

        using (MemoryMappedFile map = MemoryMappedFile.CreateFromFile(
            iso, null, 0, MemoryMappedFileAccess.ReadWrite, null, HandleInheritability.None, true))
        using (MemoryMappedViewAccessor view = map.CreateViewAccessor(0, 0, MemoryMappedFileAccess.ReadWrite))
        {
            foreach (PhysicalSegment segment in backupSegments)
            {
                view.WriteArray(segment.AbsoluteOffset, segment.Data, segment.DataOffset, segment.Length);
            }
            view.Flush();
        }
        iso.Flush(true);
        WriteOk("백업 데이터 기록 완료 (형식 v" + backupVersion + ")");
    }

    private static void ReadFully(Stream stream, byte[] buffer, int offset, int count)
    {
        while (count > 0)
        {
            int read = stream.Read(buffer, offset, count);
            if (read <= 0)
                throw new EndOfStreamException("ISO를 읽는 중 파일 끝에 도달했습니다.");
            offset += read;
            count -= read;
        }
    }

    private static bool EqualBytes(byte[] left, byte[] right)
    {
        if (left == null || right == null || left.Length != right.Length)
            return false;
        int difference = 0;
        for (int index = 0; index < left.Length; index++)
            difference |= left[index] ^ right[index];
        return difference == 0;
    }

    private static string ToHex(byte[] data)
    {
        StringBuilder result = new StringBuilder(data.Length * 2);
        foreach (byte value in data)
            result.Append(value.ToString("X2"));
        return result.ToString();
    }
}
