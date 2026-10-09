"""Le jeu est-il ouvert ? Le jeu (Game.exe) garde le coffre en mémoire et le réécrit à sa fermeture : un coffre modifié
par l'éditeur pendant que le jeu tourne serait écrasé (objet transféré vers la collection dupliqué, objet sorti de la
collection perdu). Toute écriture de coffre est donc refusée tant que le jeu est ouvert (mxl_save.commit_file).

Processus lus avec l'API Windows (ctypes, sans dépendance) : seul un Game.exe du dossier de Median XL (réglage game_dir)
bloque — « Game.exe » est un nom courant d'autres jeux ; chemin d'un Game.exe illisible : bloque (prudence). Liste des
processus impossible à lire (autre système, erreur) : pas de blocage.
"""
import os

GAME_EXE = 'game.exe'   # le jeu (Diablo II.exe n'est que le lanceur)


def running_processes():
    """[(nom de l'exécutable, n° du processus)] des processus en cours ; [] hors Windows ; None si illisible."""
    if os.name != 'nt':
        return []
    try:
        import ctypes
        from ctypes import wintypes

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD), ('th32ProcessID', wintypes.DWORD),
                        ('th32DefaultHeapID', ctypes.c_size_t), ('th32ModuleID', wintypes.DWORD),
                        ('cntThreads', wintypes.DWORD), ('th32ParentProcessID', wintypes.DWORD),
                        ('pcPriClassBase', ctypes.c_long), ('dwFlags', wintypes.DWORD),
                        ('szExeFile', ctypes.c_wchar * 260)]
        k32 = ctypes.WinDLL('kernel32', use_last_error=True)
        k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        k32.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
        k32.Process32FirstW.argtypes = k32.Process32NextW.argtypes = (wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W))
        k32.CloseHandle.argtypes = (wintypes.HANDLE,)
        snap = k32.CreateToolhelp32Snapshot(2, 0)   # TH32CS_SNAPPROCESS
        if not snap or snap == ctypes.c_void_p(-1).value:
            return None
        try:
            entry, out = PROCESSENTRY32W(), []
            entry.dwSize = ctypes.sizeof(entry)
            ok = k32.Process32FirstW(snap, ctypes.byref(entry))
            while ok:
                out.append((entry.szExeFile, entry.th32ProcessID))
                ok = k32.Process32NextW(snap, ctypes.byref(entry))
            return out
        finally:
            k32.CloseHandle(snap)
    except (OSError, AttributeError, ValueError):
        return None


def process_path(pid):
    """Chemin complet de l'exécutable d'un processus, ou None (droits insuffisants, processus terminé…)."""
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL('kernel32', use_last_error=True)
        k32.OpenProcess.restype = wintypes.HANDLE
        k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        k32.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                   ctypes.POINTER(wintypes.DWORD))
        k32.CloseHandle.argtypes = (wintypes.HANDLE,)
        h = k32.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return None
        try:
            buf, size = ctypes.create_unicode_buffer(1024), wintypes.DWORD(1024)
            return buf.value if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)) else None
        finally:
            k32.CloseHandle(h)
    except (OSError, AttributeError, ValueError):
        return None


def running_game(game_dir):
    """Le jeu Median XL ouvert : chemin de son Game.exe (ou « Game.exe » si le chemin est illisible), sinon None.
    game_dir inconnu : tout Game.exe compte."""
    procs = running_processes()
    if not procs:
        return None
    root = os.path.normcase(os.path.abspath(game_dir)) if game_dir else None
    for name, pid in procs:
        if name.lower() != GAME_EXE:
            continue
        path = process_path(pid)
        if path is None or root is None:
            return path or name   # chemin illisible ou dossier du jeu inconnu : bloque par prudence
        if os.path.normcase(os.path.abspath(path)).startswith(root + os.sep):
            return path
    return None
