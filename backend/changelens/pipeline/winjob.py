"""Windows Job Object caps for the parse sandbox (ctypes; Windows has no setrlimit).

The child is assigned before it receives the document, so its parse runs entirely under the caps:
per-process committed memory, per-process user CPU time, one active process (no grandchildren),
and kill-on-close. Limitation: the child runs its interpreter start-up briefly before assignment.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes

JobObjectBasicAccountingInformation = 1
JobObjectExtendedLimitInformation = 9
LIMIT_PROCESS_TIME = 0x2
LIMIT_ACTIVE_PROCESS = 0x8
LIMIT_PROCESS_MEMORY = 0x100
LIMIT_DIE_ON_UNHANDLED_EXCEPTION = 0x400
LIMIT_KILL_ON_JOB_CLOSE = 0x2000


class _Basic(ctypes.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD)]


class _Io(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint64) for n in ("ReadOps", "WriteOps", "OtherOps", "ReadBytes",
                                               "WriteBytes", "OtherBytes")]


class _Extended(ctypes.Structure):
    _fields_ = [("Basic", _Basic), ("Io", _Io), ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t)]


class _Accounting(ctypes.Structure):
    _fields_ = [("TotalUserTime", ctypes.c_int64), ("TotalKernelTime", ctypes.c_int64),
                ("ThisPeriodTotalUserTime", ctypes.c_int64), ("ThisPeriodTotalKernelTime", ctypes.c_int64),
                ("TotalPageFaultCount", wintypes.DWORD), ("TotalProcesses", wintypes.DWORD),
                ("ActiveProcesses", wintypes.DWORD), ("TotalTerminatedProcesses", wintypes.DWORD)]


_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_k32.CreateJobObjectW.restype = wintypes.HANDLE
_k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
_k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
_k32.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
                                           ctypes.c_void_p]
_k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
_k32.CloseHandle.argtypes = [wintypes.HANDLE]


def _check(ok) -> None:
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())


def confine(proc, memory_bytes: int, cpu_seconds: int):
    """Create a job with the caps and put `proc` (a subprocess.Popen) in it. Returns the job handle."""
    job = _k32.CreateJobObjectW(None, None)
    _check(job)
    info = _Extended()
    info.Basic.LimitFlags = (LIMIT_PROCESS_MEMORY | LIMIT_PROCESS_TIME | LIMIT_ACTIVE_PROCESS
                             | LIMIT_DIE_ON_UNHANDLED_EXCEPTION | LIMIT_KILL_ON_JOB_CLOSE)
    info.Basic.PerProcessUserTimeLimit = int(cpu_seconds * 10_000_000)  # 100 ns units
    info.Basic.ActiveProcessLimit = 1
    info.ProcessMemoryLimit = memory_bytes
    try:
        _check(_k32.SetInformationJobObject(job, JobObjectExtendedLimitInformation, ctypes.byref(info),
                                            ctypes.sizeof(info)))
        _check(_k32.AssignProcessToJobObject(job, int(proc._handle)))
    except OSError:
        proc.kill()
        _k32.CloseHandle(job)
        raise
    return job


def usage(job) -> tuple[int, float]:
    """(peak committed bytes of any process in the job, total user CPU seconds)."""
    ext, acc = _Extended(), _Accounting()
    _check(_k32.QueryInformationJobObject(job, JobObjectExtendedLimitInformation, ctypes.byref(ext),
                                          ctypes.sizeof(ext), None))
    _check(_k32.QueryInformationJobObject(job, JobObjectBasicAccountingInformation, ctypes.byref(acc),
                                          ctypes.sizeof(acc), None))
    return ext.PeakProcessMemoryUsed, acc.TotalUserTime / 10_000_000


def close(job) -> None:
    _k32.CloseHandle(job)
