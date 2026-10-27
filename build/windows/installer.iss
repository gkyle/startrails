#ifndef StageDir
  #error Build with build/windows/build.ps1 to supply the staged release.
#endif
#if Ver < EncodeVer(6, 7, 1)
  #error Inno Setup 6.7.1 or later is required.
#endif
#include AddBackslash(StageDir) + "build_config.iss"
#define ReleaseDir "{app}\releases\" + ReleaseId
#define SetupScript ReleaseDir + "\src\setup\setup.ps1"
#define PowerShell "{sys}\WindowsPowerShell\v1.0\powershell.exe"

[Setup]
AppId=StarTrailsAI
AppName=StarTrails AI
AppVersion={#AppVersion}
AppPublisher=StarTrails contributors
AppPublisherURL=https://github.com/gkyle/startrails
DefaultDirName={localappdata}\Programs\StarTrails
DefaultGroupName=StarTrails AI
PrivilegesRequired=lowest
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
MinVersion=10.0.19045
LicenseFile={#StageDir}\app\LICENSE
SetupIconFile={#StageDir}\app\resources\startrails.ico
UninstallDisplayIcon={#ReleaseDir}\resources\startrails.ico
OutputBaseFilename=StarTrailsAI-{#AppVersion}-windows-x64-setup
Compression=lzma2/fast
SolidCompression=yes
ArchiveExtraction=full
WizardStyle=modern
CloseApplications=no
#ifdef SignedBuild
SignTool=startrails
SignedUninstaller=yes
#endif

[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "{#StageDir}\{#ApplicationName}"; Flags: dontcopy
; Register the prepared files with the uninstaller only after prerequisites succeed.
Source: "{tmp}\{#ApplicationName}"; DestDir: "{#ReleaseDir}"; ExternalSize: {#ApplicationSize}; Flags: external extractarchive ignoreversion recursesubdirs
Source: "{tmp}\{#ModelsName}"; DestDir: "{#ReleaseDir}"; ExternalSize: {#ModelsSize}; Hash: "{#ModelsHash}"; Flags: external extractarchive ignoreversion recursesubdirs

[Icons]
Name: "{group}\StarTrails AI"; Filename: "{#PowerShell}"; Parameters: "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File ""{#SetupScript}"" -Packaged -Launch"; WorkingDir: "{#ReleaseDir}"; IconFilename: "{#ReleaseDir}\resources\startrails.ico"; AppUserModelID: "{#AppUserModelId}"; Flags: runminimized
Name: "{group}\Repair StarTrails AI"; Filename: "{#PowerShell}"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{#SetupScript}"" -Packaged -Repair"; WorkingDir: "{#ReleaseDir}"; IconFilename: "{#ReleaseDir}\resources\startrails.ico"
Name: "{autodesktop}\StarTrails AI"; Filename: "{#PowerShell}"; Parameters: "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File ""{#SetupScript}"" -Packaged -Launch"; WorkingDir: "{#ReleaseDir}"; IconFilename: "{#ReleaseDir}\resources\startrails.ico"; AppUserModelID: "{#AppUserModelId}"; Tasks: desktopicon; Flags: runminimized

[Run]
Filename: "{#PowerShell}"; Parameters: "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File ""{#SetupScript}"" -Packaged -Launch"; Description: "Launch StarTrails AI"; Flags: nowait postinstall skipifsilent runminimized

[UninstallDelete]
; Dependency wheels contain paths longer than MAX_PATH. Use the extended-length
; prefix for the application-owned directories; user working directories are separate.
Type: filesandordirs; Name: "\\?\{app}\releases"
Type: filesandordirs; Name: "\\?\{localappdata}\StarTrails\cache"

[Code]
const
  MaxDisplayedSetupLines = 200;
  EM_SCROLLCARET = $00B7;

var
  DownloadPage: TDownloadWizardPage;
  RuntimePage: TOutputMarqueeProgressWizardPage;
  SetupOutput: TNewMemo;

procedure LogSetupOutput(const S: String; const Error, FirstLine: Boolean);
begin
  Log(S);
  if Trim(S) = '' then
    Exit;
  if SetupOutput.Lines.Count >= MaxDisplayedSetupLines then
    SetupOutput.Lines.Delete(0);
  SetupOutput.Lines.Add(S);
  SetupOutput.SelStart := Length(SetupOutput.Text);
  SendMessage(SetupOutput.Handle, EM_SCROLLCARET, 0, 0);
end;

procedure InitializeWizard;
begin
  DownloadPage := CreateDownloadPage('Downloading models', 'Preparing StarTrails AI models...', nil);
  DownloadPage.ShowBaseNameInsteadOfUrl := True;
  RuntimePage := CreateOutputMarqueeProgressPage('Installing Python and dependencies',
    'Preparing StarTrails AI for this computer. This may take several minutes.');
  SetupOutput := TNewMemo.Create(RuntimePage);
  SetupOutput.Parent := RuntimePage.Surface;
  SetupOutput.SetBounds(0,
    RuntimePage.ProgressBar.Top + RuntimePage.ProgressBar.Height + ScaleY(12),
    RuntimePage.SurfaceWidth,
    RuntimePage.SurfaceHeight - RuntimePage.ProgressBar.Top - RuntimePage.ProgressBar.Height - ScaleY(12));
  SetupOutput.ReadOnly := True;
  SetupOutput.ScrollBars := ssVertical;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
  SetupLog: String;
  PrerequisiteNotice: AnsiString;
  ModelArchive: String;
  ModelCache: String;
  ReusedModels: Boolean;
begin
  Result := '';
  try
    ModelArchive := ExpandConstant('{tmp}\{#ModelsName}');
    ModelCache := ExpandConstant('{localappdata}\StarTrails\cache\models.zip');
    ReusedModels := False;
    if FileExists(ModelCache) then begin
      try
        if CompareText(GetSHA256OfFile(ModelCache), '{#ModelsHash}') = 0 then begin
          ReusedModels := CopyFile(ModelCache, ModelArchive, False);
          if ReusedModels then
            Log('Reusing verified model archive from ' + ModelCache);
        end;
      except
        Log('Could not reuse cached model archive: ' + GetExceptionMessage);
      end;
    end;
    if not ReusedModels then begin
      if FileExists(ModelArchive) and not DeleteFile(ModelArchive) then
        RaiseException('Could not replace the temporary model archive.');
      DownloadPage.Clear;
      DownloadPage.Add('{#ModelsUrl}', '{#ModelsName}', '{#ModelsHash}');
      DownloadPage.Show;
      try
        DownloadPage.Download;
      finally
        DownloadPage.Hide;
      end;
      if ForceDirectories(ExtractFileDir(ModelCache)) then begin
        if not CopyFile(ModelArchive, ModelCache, False) then
          Log('Could not cache the verified model archive for the next installation.');
      end else
        Log('Could not create the model cache directory.');
    end;
    ExtractTemporaryFile('{#ApplicationName}');
    ForceDirectories(ExpandConstant('{#ReleaseDir}'));
    ExtractArchive(ExpandConstant('{tmp}\{#ApplicationName}'), ExpandConstant('{#ReleaseDir}'), '', True, nil);
    ExtractArchive(ExpandConstant('{tmp}\{#ModelsName}'), ExpandConstant('{#ReleaseDir}'), '', True, nil);
    SetupLog := ExpandConstant('{#ReleaseDir}\runtime\setup.log');
    SetupOutput.Clear;
    RuntimePage.SetText('Installing Python and application dependencies...',
      'Download and installation activity appears below.');
    RuntimePage.Show;
    RuntimePage.Animate;
    try
      if not ExecAndLogOutput(ExpandConstant('{#PowerShell}'),
        ExpandConstant('-NoProfile -ExecutionPolicy Bypass -File "{#SetupScript}" -Packaged'),
        ExpandConstant('{#ReleaseDir}'), SW_HIDE, ewWaitUntilTerminated, ResultCode, @LogSetupOutput) then
        RaiseException('Could not start Python setup. Please run this installer again.');
    finally
      RuntimePage.Hide;
    end;
    if ResultCode <> 0 then
      RaiseException('Python setup failed. See the setup log for details, then run this installer again.' + #13#10 +
        'Setup log: ' + SetupLog);
    if LoadStringFromFile(ExpandConstant('{#ReleaseDir}\runtime\prerequisites.txt'), PrerequisiteNotice) then
      if PrerequisiteNotice <> '' then
        SuppressibleMsgBox(String(PrerequisiteNotice), mbInformation, MB_OK, IDOK);
  except
    Result := GetExceptionMessage;
  end;
end;
