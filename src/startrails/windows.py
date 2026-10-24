"""Windows shell identity shared by the running application and its installer."""

# Keep this stable across upgrades so pinned shortcuts still identify the app.
APP_USER_MODEL_ID = "StarTrails.StarTrailsAI"


def configure_taskbar_identity():
    """Identify StarTrails before Qt creates any windows."""
    try:
        import ctypes

        shell = ctypes.OleDLL("shell32")
        set_app_id = shell.SetCurrentProcessExplicitAppUserModelID
        set_app_id.argtypes = [ctypes.c_wchar_p]
        set_app_id.restype = ctypes.HRESULT
        set_app_id(APP_USER_MODEL_ID)
    except Exception:
        # Failure to register taskbar identity should not prevent application launch.
        pass
