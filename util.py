import base64
import ctypes
import datetime
import hashlib
import inspect
import json
import math
import os
import pathlib
import platform
import random
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import traceback
import uuid
import webbrowser
from functools import wraps
from typing import Callable, Optional
from urllib import parse

import psutil
import requests.exceptions
import selenium.common.exceptions
import toml
import urllib3.exceptions

from compress import (compress_in_memory_with_lzma,
                      decompress_in_memory_with_lzma)
from const import cached_dir
from db import *
from log import asciiReset, color, get_log_func, logger
from version import now_version, ver_time


def is_windows() -> bool:
    return platform.system() == "Windows"


if is_windows():
    import win32api
    import win32con
    import win32gui
    import win32process

if is_windows():
    MB_ICONINFORMATION = win32con.MB_ICONINFORMATION
else:
    MB_ICONINFORMATION = 64


def uin2qq(uin):
    return str(uin)[1:].lstrip('0')


def is_valid_qq(qq: str) -> bool:
    return qq.isnumeric()


def change_console_window_mode_async(disable_min_console=False):
    if is_run_in_pycharm():
        logger.info("当前运行在pycharm中，不尝试调整窗口大小~")
        return

    from copy import deepcopy

    from config import Config, config

    cfg = Config()
    try:
        cfg = deepcopy(config())
    except Exception as e:
        logger.error(f"读取配置失败", exc_info=e)

    # 如果是windows系统的话，先尝试同步设置cmd属性
    ensure_cmd_window_buffer_size_for_windows(cfg)

    threading.Thread(target=change_console_window_mode, args=(cfg, disable_min_console), daemon=True).start()


def ensure_cmd_window_buffer_size_for_windows(cfg):
    if platform.system() != "Windows":
        logger.info(f"当前运行的系统是{platform.system()}，将不尝试 修改cmd缓存")
        return

    if not cfg.common.enable_change_cmd_buffer:
        logger.info(color("bold_yellow") + "当前配置为不尝试修改命令行缓存大小，运行日志有可能被截断~")
        return

    # windows下需要强制修改缓存区到足够大，这样点最大化时才能铺满全屏幕
    base_width = 1920
    base_cols = 240

    width, height = get_screen_size()
    cols = math.floor(width / base_width * base_cols)
    lines = 9999

    os.system(f"mode con:cols={cols} lines={lines}")
    logger.info(color("bold_cyan") + f"当前是windows系统，分辨率为{width}*{height}，强制修改窗口大小为{lines}行*{cols}列，以确保运行日志能不被截断。如不想启用该功能，请关闭【修改命令行缓存大小】开关")


def change_console_window_mode(cfg, disable_min_console=False):
    if platform.system() != "Windows":
        logger.info(f"当前运行的系统是{platform.system()}，将不尝试 修改窗口大小")
        return

    logger.info(color("bold_cyan") + "准备最大化运行窗口，请稍候。若想修改该配置，请前往配置工具调整该选项~")

    try_set_console_window_mode(win32con.SW_MAXIMIZE, "最大化窗口", cfg.common.enable_max_console)
    try_set_console_window_mode(win32con.SW_MINIMIZE, "最小化窗口", cfg.common.enable_min_console and not disable_min_console)


def try_set_console_window_mode(show_mode: int, mode_name: str, mode_enabled: bool):
    """
    调用win32gui.ShowWindow设置当前cmd所在窗口的显示模式，可选值为[win32con.SW_MAXIMIZE, win32con.SW_MINIMIZE]
    """
    # 判断是否需要尝试修改为对应窗口模式
    if not mode_enabled:
        logger.info(color("bold_cyan") + f"当前未开启 {mode_name} 配置，将不尝试{mode_name}")
        return

    # 开始设置
    logger.info(color("bold_cyan") + f"当前已开启 {mode_name} 配置，将尝试{mode_name}")

    current_pid = os.getpid()
    parents = get_parents(current_pid)

    # 找到所有窗口中在该当前进程到进程树的顶端之间路径的窗口
    candidates_index_to_hwnd = {}

    def max_current_console(hwnd, argument):
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if pid in parents:
            # 记录下他们在进程树路径的下标
            argument[parents.index(pid)] = hwnd

    # 遍历所有窗口
    win32gui.EnumWindows(max_current_console, candidates_index_to_hwnd)

    # 排序，从而找到最接近的那个，就是我们所需的当前窗口
    indexes = sorted(list(candidates_index_to_hwnd.keys()))
    current_hwnd = candidates_index_to_hwnd[indexes[0]]

    win32gui.ShowWindow(current_hwnd, show_mode)


def exists_flag_file(flag_file_name: str) -> bool:
    return os.path.exists(flag_file_name)


def get_parents(child):
    parents = [child]

    try:
        current = child
        while True:
            parent = psutil.Process(current).ppid()
            parents.append(parent)
            current = parent
    except psutil.NoSuchProcess:
        # 遍历到进程树最顶层仍未找到parent，说明不是父子关系
        pass

    return parents


def printed_width(msg):
    return sum([1 if ord(c) < 128 else 2 for c in msg])


def split_by_printed_width(msg: str, expect_width: int) -> Tuple[str, str]:
    if printed_width(msg) <= expect_width:
        return msg, ""

    index = 0
    current_width = 0
    for substr in msg:
        current_width += printed_width(substr)
        if current_width > expect_width:
            break
        index += len(substr)

    return msg[:index], msg[index:]


def truncate(msg, expect_width) -> str:
    if printed_width(msg) <= expect_width:
        return msg

    truncated = []
    current_width = 3
    for substr in msg:
        current_width += printed_width(substr)
        if current_width > expect_width:
            truncated.append("...")
            break
        truncated.append(substr)

    return ''.join(truncated)


def padLeftRight(msg, target_size, pad_char=" ", mode="middle", need_truncate=False):
    msg = str(msg)
    if need_truncate:
        msg = truncate(msg, target_size)
    msg_len = printed_width(msg)
    pad_left_len, pad_right_len = 0, 0
    if msg_len < target_size:
        total = target_size - msg_len
        pad_left_len = total // 2
        pad_right_len = total - pad_left_len

    if mode == "middle":
        return pad_char * pad_left_len + msg + pad_char * pad_right_len
    elif mode == "left":
        return msg + pad_char * (pad_left_len + pad_right_len)
    else:
        return pad_char * (pad_left_len + pad_right_len) + msg


def tableify(cols, colSizes, delimiter=' ', need_truncate=False):
    return delimiter.join([padLeftRight(col, colSizes[idx], need_truncate=need_truncate) for idx, col in enumerate(cols)])


def show_head_line(msg, msg_color=color("fg_bold_green"), max_line_content_width=80, min_line_printed_width=80):
    msg = split_line_if_too_long(msg, max_line_content_width)
    line_width = max(min_line_printed_width, get_max_line_width(msg))

    # 按照下列格式打印
    # ┌──────────┐
    # │   test   │
    # │   test   │
    # │   test   │
    # └──────────┘
    logger.info(get_meaningful_call_point_for_log())
    logger.warning("┌" + "─" + "─" * line_width + "┐")
    for line in msg.splitlines():
        logger.warning("│" + " " + msg_color + padLeftRight(line, line_width) + asciiReset + color("WARNING") + "│")
    logger.warning("└" + "─" + "─" * line_width + "┘")


def split_line_if_too_long(msg: str, max_line_width) -> str:
    # 确保每行不超过指定大小，超过的行分割为若干个符合条件的行，并在末尾增加\n来标记
    padding = "\\n"
    padding_width = printed_width(padding)

    lines = []
    for line in msg.splitlines():
        while printed_width(line) > max_line_width:
            fitted_line, line = split_by_printed_width(line, max_line_width - padding_width)
            lines.append(fitted_line + padding)

        lines.append(line)

    return "\n".join(lines)


def get_max_line_width(msg: str) -> int:
    line_length = 0
    for line in msg.splitlines():
        line_length = max(line_length, printed_width(line))

    return line_length


def get_now() -> datetime:
    return datetime.datetime.now()


def get_this_week_monday(now=get_now()) -> str:
    return get_this_week_monday_datetime(now).strftime("%Y%m%d")


def get_last_week_monday(now=get_now()) -> str:
    lastWeekMonday = get_this_week_monday_datetime(now) - datetime.timedelta(days=7)
    return lastWeekMonday.strftime("%Y%m%d")


def get_this_week_monday_datetime(now=get_now()) -> datetime.datetime:
    monday = now - datetime.timedelta(days=now.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def now_before(t="2000-01-01 00:00:00"):
    return get_now() < parse_time(t)


def now_after(t="2000-01-01 00:00:00"):
    return get_now() >= parse_time(t)


def now_in_range(left="2000-01-01 00:00:00", right="3000-01-01 00:00:00"):
    return now_after(left) and now_before(right)


def get_now_unix(now=get_now()) -> int:
    return int(now.timestamp())


def get_current(t=get_now()) -> str:
    return t.strftime("%Y%m%d%H%M%S")


def get_today(t=get_now()) -> str:
    return t.strftime("%Y%m%d")


def get_last_n_days(n, now=get_now()) -> List[str]:
    return [(now - datetime.timedelta(i)).strftime("%Y%m%d") for i in range(1, n + 1)]


def get_week(t=get_now()) -> str:
    return t.strftime("%Y-week-%W")


def get_month(t=get_now()) -> str:
    return t.strftime("%Y%m")


def get_year(t=get_now()) -> str:
    return t.strftime("%Y")


def filter_unused_params(urlRendered: str) -> str:
    path = ""
    if '?' in urlRendered:
        # https://www.example.com/index?a=1&b=2
        idx = urlRendered.index('?')
        path, urlRendered = urlRendered[:idx], urlRendered[idx + 1:]
    elif '=' in urlRendered or '&' in urlRendered:
        # a=1&b=2
        path, urlRendered = "", urlRendered
    else:
        # https://www.example.com/index
        path, urlRendered = urlRendered, ""

    parts = urlRendered.split('&')

    validParts = []
    for part in parts:
        if part == "":
            continue
        k, v = part.split('=', maxsplit=1)
        if v != "":
            validParts.append(part)

    newUrl = path
    if len(validParts) != 0:
        if len(path) != 0:
            newUrl = path + "?" + '&'.join(validParts)
        else:
            newUrl = '&'.join(validParts)

    return newUrl


def filter_unused_params_catch_exception(urlRendered: str) -> str:
    originalUrl = urlRendered
    try:
        return filter_unused_params(urlRendered)
    except Exception as e:
        logger.error(f"过滤参数出错了，urlRendered={originalUrl}", exc_info=e)
        stack_info = color("bold_black") + ''.join(traceback.format_stack())
        logger.error(f"看到上面这个报错，请帮忙截图发反馈群里~ 调用堆栈=\n{stack_info}")
        return originalUrl


def run_from_src() -> bool:
    exe_path = sys.argv[0]
    _, filename = os.path.dirname(exe_path), os.path.basename(exe_path)

    return filename.endswith(".py") or filename == "pytest"


def get_uuid() -> str:
    return f"{platform.node()}-{uuid.getnode()}"


def use_by_myself() -> bool:
    return exists_flag_file(".use_by_myself")


def try_except(show_exception_info=True, show_last_process_result=True, extra_msg="", return_val_on_except=None) -> Callable:
    def decorator(fun):
        @wraps(fun)
        def wrapper(*args, **kwargs):
            try:
                return fun(*args, **kwargs)
            except Exception as e:
                msg = f"执行{fun.__name__}({args}, {kwargs})出错了"
                if extra_msg != "":
                    msg += ", " + extra_msg
                msg += check_some_exception(e, show_last_process_result)

                logFunc = logger.error
                if not show_exception_info:
                    logFunc = logger.debug
                logFunc(msg, exc_info=e)

                return return_val_on_except

        return wrapper

    return decorator


def with_retry(max_retry_count=3, retry_wait_time=5, show_exception_info=True) -> Callable:
    def decorator(fun):
        @wraps(fun)
        def wrapper(*args, **kwargs):
            for i in range(max_retry_count):
                try:
                    return fun(*args, **kwargs)
                except Exception as exc:
                    msg = f"第 {i + 1}/{max_retry_count} 次 尝试执行{fun.__name__}({args}, {kwargs})出错了"
                    msg += check_some_exception(exc, True)
                    logFunc = logger.error
                    if not show_exception_info:
                        logFunc = logger.debug

                    logFunc(msg, exc_info=exc)
                    if i + 1 != max_retry_count:
                        logFunc(f"等待 {retry_wait_time} 秒后重试")
                        time.sleep(retry_wait_time)

            exc_msg = f"重试{max_retry_count}次后仍失败"
            logger.error(exc_msg)
            raise Exception(exc_msg)

        return wrapper

    return decorator


def check_some_exception(e: Exception, show_last_process_result=True) -> str:
    msg = ""

    def format_msg(msg, _color="bold_yellow"):
        return "\n" + color(_color) + msg + asciiReset

    # 特判一些错误
    if type(e) is KeyError and e.args[0] == 'modRet':
        msg += format_msg("大概率是这个活动过期了，或者放鸽子到点了还没开放，若影响正常运行流程，可先自行关闭这个活动开关(若config.toml中没有，请去config.example.toml找到对应开关名称)，或等待新版本（日常加班，有时候可能会很久才发布新版本）")
    elif type(e) in [socket.timeout,
                     urllib3.exceptions.ConnectTimeoutError, urllib3.exceptions.MaxRetryError, urllib3.exceptions.ReadTimeoutError,
                     requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout, ]:
        msg += format_msg("网络超时了，一般情况下是因为网络问题，也有可能是因为对应网页的服务器不太行，多试几次就好了<_<")
    elif type(e) in [selenium.common.exceptions.TimeoutException, ]:
        msg += format_msg("浏览器等待对应元素超时了，很常见的。如果一直超时导致无法正常运行，可去config.example.toml将登录超时相关配置加到config.toml中，并调大超时时间")
    elif type(e) in [PermissionError, ]:
        msg += format_msg((
            "权限错误一般是以下原因造成的\n"
            "1. 该文件被占用，比如打开了多个小助手实例或者其他应用占用了这些文件，可以尝试重启电脑后再运行\n"
            "2. 开启了VPN，请尝试关闭VPN后再运行（看上去毫不相关，但确实会这样- -）"
        ))

    if show_last_process_result:
        from network import last_response_info
        if last_response_info is not None:
            lr = last_response_info
            text = parse_unicode_escape_string(lr.text)
            msg += format_msg(f"最近一次收到的请求结果为：status_code={lr.status_code} reason={lr.reason} \n{text}", "bold_cyan")

    return msg


def is_act_expired(end_time: str, time_fmt="%Y-%m-%d %H:%M:%S", now=get_now()) -> bool:
    return datetime.datetime.strptime(end_time, time_fmt) < now


def will_act_expired_in(end_time: str, duration: datetime.timedelta, time_fmt="%Y-%m-%d %H:%M:%S", now=get_now()) -> bool:
    return datetime.datetime.strptime(end_time, time_fmt) < now + duration


def get_remaining_time(end_time, time_fmt="%Y-%m-%d %H:%M:%S", now=get_now()) -> datetime.timedelta:
    return datetime.datetime.strptime(end_time, time_fmt) - now


def get_past_time(t, time_fmt="%Y-%m-%d %H:%M:%S", now=get_now()) -> datetime.timedelta:
    return now - datetime.datetime.strptime(t, time_fmt)


def show_end_time(end_time, time_fmt="%Y-%m-%d %H:%M:%S"):
    # end_time = "2021-02-23 00:00:00"
    remaining_time = get_remaining_time(end_time, time_fmt)
    logger.info(color("bold_black") + f"活动的结束时间为{end_time}，剩余时间为{remaining_time}")


def time_less(left_time_str, right_time_str, time_fmt="%Y-%m-%d %H:%M:%S") -> bool:
    left_time = datetime.datetime.strptime(left_time_str, time_fmt)
    right_time = datetime.datetime.strptime(right_time_str, time_fmt)

    return left_time < right_time


def parse_time(time_str, time_fmt="%Y-%m-%d %H:%M:%S") -> datetime.datetime:
    return datetime.datetime.strptime(time_str, time_fmt)


def parse_timestamp(ts: float) -> datetime.datetime:
    return datetime.datetime.fromtimestamp(ts)


def format_time(dt, time_fmt="%Y-%m-%d %H:%M:%S"):
    return dt.strftime(time_fmt)


def format_now(time_fmt="%Y-%m-%d %H:%M:%S", now=get_now()):
    return format_time(now, time_fmt=time_fmt)


def format_timestamp(ts: float):
    return format_time(parse_timestamp(ts))


def async_call(cb, *args, **params):
    threading.Thread(target=cb, args=args, kwargs=params, daemon=True).start()


def async_message_box(msg, title, print_log=True, icon=MB_ICONINFORMATION, open_url="", show_once=False, follow_flag_file=True, color_name="bold_cyan"):
    async_call(message_box, msg, title, print_log, icon, open_url, show_once, follow_flag_file, color_name)


def message_box(msg, title, print_log=True, icon=MB_ICONINFORMATION, open_url="", show_once=False, follow_flag_file=True, color_name="bold_cyan"):
    get_log_func(logger.warning, print_log)(color(color_name) + msg)

    if is_run_in_github_action():
        return

    from first_run import is_first_run

    show_message_box = True
    if show_once and not is_first_run(f"message_box_{title}"):
        show_message_box = False
    if follow_flag_file and exists_flag_file('.no_message_box'):
        show_message_box = False

    if show_message_box and is_windows():
        win32api.MessageBox(0, msg, title, icon)

    if open_url != "":
        webbrowser.open(open_url)


KiB = 1024
MiB = 1024 * KiB
GiB = 1024 * MiB
TiB = 1024 * GiB
PiB = 1024 * TiB
EiB = 1024 * PiB
ZiB = 1024 * EiB
YiB = 1024 * ZiB


def human_readable_size(num, suffix='B') -> str:
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


@try_except()
def clean_dir_to_size(dir_name: str, max_logs_size: int = 1024 * MiB, keep_logs_size: int = 512 * MiB):
    # 检查一下是否存在目录
    if not os.path.isdir(dir_name):
        return

    hrs = human_readable_size

    logger.info(color("bold_green") + f"尝试清理日志目录({dir_name})，避免日志目录越来越大~")

    logs_size = get_directory_size(dir_name)
    if logs_size <= max_logs_size:
        logger.info(f"当前日志目录大小为{hrs(logs_size)}，未超出设定最大值为{hrs(max_logs_size)}，无需清理")
        return

    logger.info(f"当前日志目录大小为{hrs(logs_size)}，超出设定最大值为{hrs(max_logs_size)}，将按照时间顺序移除部分日志，直至不高于设定清理后剩余大小{hrs(keep_logs_size)}")

    # 获取全部日志文件，并按照时间升序排列
    logs = list(pathlib.Path(dir_name).glob('**/*'))

    def sort_key(f: pathlib.Path):
        return f.stat().st_mtime

    logs.sort(key=sort_key)

    # 清除日志，直至剩余日志大小低于设定值
    remaining_logs_size = logs_size
    remove_log_count = 0
    remove_log_size = 0
    for log_file in logs:
        stat = log_file.stat()
        remaining_logs_size -= stat.st_size
        remove_log_count += 1
        remove_log_size += stat.st_size

        os.remove(f"{log_file}")
        logger.info(f"移除第{remove_log_count}个日志:{log_file.name} 大小：{hrs(stat.st_size)}，剩余日志大小为{hrs(remaining_logs_size)}")

        if remaining_logs_size <= keep_logs_size:
            logger.info(color("bold_green") + f"当前剩余日志大小为{hrs(remaining_logs_size)}，将停止日志清理流程~ 本次累计清理{remove_log_count}个日志文件，总大小为{hrs(remove_log_size)}")
            break


def get_directory_size(dir_name: str) -> int:
    root_directory = pathlib.Path(dir_name)
    return sum(f.stat().st_size for f in root_directory.glob('**/*') if f.is_file())


def get_random_face() -> str:
    return random.choice([
        'ヾ(◍°∇°◍)ﾉﾞ', 'ヾ(✿ﾟ▽ﾟ)ノ', 'ヾ(๑╹◡╹)ﾉ"', '٩(๑❛ᴗ❛๑)۶', '٩(๑-◡-๑)۶ ',
        'ヾ(●´∀｀●) ', '(｡◕ˇ∀ˇ◕)', '(◕ᴗ◕✿)', '✺◟(∗❛ัᴗ❛ั∗)◞✺', '(づ｡◕ᴗᴗ◕｡)づ',
        '(≧∀≦)♪', '♪（＾∀＾●）ﾉ', '(●´∀｀●)ﾉ', "(〃'▽'〃)", '(｀・ω・´)',
        'ヾ(=･ω･=)o', '(◍´꒳`◍)', '(づ●─●)づ', '｡◕ᴗ◕｡', '●﹏●',
    ])


def clear_login_status():
    # 获取全部日志文件，并按照时间升序排列
    saved_login_cache_files = list(pathlib.Path(cached_dir).glob('.saved_*'))
    for cache_file in saved_login_cache_files:
        os.remove(cache_file)
        logger.info(f"移除缓存的登录信息：{cache_file}")


def get_screen_size() -> Tuple[int, int]:
    """
    :return: 屏幕宽度和高度
    """
    if not is_windows():
        return 1920, 1080

    width, height = win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1)
    return width, height


def make_sure_dir_exists(dir_path):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)


def is_run_in_github_action():
    return get_config_from_env() != ""


def get_config_from_env() -> str:
    # 先尝试第一个环境变量，直接获取 toml_str
    toml_str = os.environ.get("DJC_HELPER_CONFIG_TOML", "")
    if toml_str != "":
        return toml_str

    # 如果对应运行环境不方便设置多行的环境变量，则分别尝试可以单行的编码格式
    # toml 配置编码为 base64
    base64_str = os.environ.get("DJC_HELPER_CONFIG_BASE64", "")
    if base64_str != "":
        return base64_to_toml(base64_str)

    # toml 配置先通过 lzma 压缩，然后编码为 base64
    compressed_base64_str = os.environ.get("DJC_HELPER_CONFIG_LZMA_COMPRESSED_BASE64", "")
    if compressed_base64_str != "":
        return base64_to_toml(compressed_base64_str, compress_before_encode=True)

    # toml 配置解析后再序列化为单行的 JSON 配置
    json_str = os.environ.get("DJC_HELPER_CONFIG_SINGLE_LINE_JSON", "")
    if json_str != "":
        return json_to_toml(json_str)

    return ""


def gen_config_for_github_action_base64(github_action_config_path='config.toml.github_action', compress_before_encode=False):
    ctx = "base64版本"
    target_filepath = f"{github_action_config_path}.base64"
    if compress_before_encode:
        ctx += "(压缩后转码)"
        target_filepath = f"{github_action_config_path}.compressed.base64"

    with open(github_action_config_path, 'r', encoding='utf-8') as toml_file:
        with open(target_filepath, 'w', encoding='utf-8') as save_file:
            toml_bytes = toml_file.read().encode()
            if compress_before_encode:
                toml_bytes = compress_in_memory_with_lzma(toml_bytes)
            base64_version = base64.standard_b64encode(toml_bytes).decode()
            save_file.write(base64_version)

    show_file_content_info(ctx, pathlib.Path(target_filepath).read_text())


def gen_config_for_github_action_json_single_line(github_action_config_path='config.toml.github_action'):
    target_filepath = f"{github_action_config_path}.json"

    with open(github_action_config_path, 'r', encoding='utf-8') as toml_file:
        with open(target_filepath, 'w', encoding='utf-8') as save_file:
            cfg = toml.load(toml_file)
            json.dump(cfg, save_file)

    show_file_content_info("json版本", pathlib.Path(target_filepath).read_text())


def show_file_content_info(ctx: str, file_content: str):
    total_size = len(file_content)
    total_lines = file_content.count('\n') + 1
    logger.info(f"{ctx} 生成配置文件大小为{total_size}({human_readable_size(total_size)})，总行数为{total_lines}")


def base64_to_toml(github_action_config_base64: str, compress_before_encode=False) -> str:
    toml_bytes = base64.standard_b64decode(github_action_config_base64.encode())
    if compress_before_encode:
        toml_bytes = decompress_in_memory_with_lzma(toml_bytes)

    return toml_bytes.decode()


def json_to_toml(github_action_config_json: str) -> str:
    return toml.dumps(json.loads(github_action_config_json))


def disable_pause_after_run() -> bool:
    return exists_flag_file(".disable_pause_after_run")


# 解析文件中的unicode编码字符串，形如\u5df2，将其转化为可以直观展示的【已】，目前用于查看github action的日志
def remove_invalid_unicode_escape_string_in_file(filename: str):
    with open(filename, 'r', encoding='utf-8') as f:
        print(remove_invalid_unicode_escape_string(f.read()))


def remove_invalid_unicode_escape_string(contents: str) -> str:
    invalid_chars = []
    for code in range(ord('g'), ord('z') + 1):
        invalid_chars.append(chr(code))
    for code in range(ord('G'), ord('Z') + 1):
        invalid_chars.append(chr(code))
    for char in invalid_chars:
        contents = contents.replace(f"u{char}", f"u0020u{char}")

    return parse_unicode_escape_string(contents)


def parse_unicode_escape_string(escaped_string: str) -> str:
    return escaped_string.encode().decode("unicode-escape")


def remove_none_from_list(vlist: list) -> list:
    return list(filter(lambda x: x is not None, vlist))


_root_caches_key = "caches"
cache_name_download = "download_cache"
cache_name_user_buy_info = "user_buy_info"


def with_cache(cache_category: str, cache_key: str, cache_miss_func: Callable[[], Any], cache_validate_func: Optional[Callable[[Any], bool]] = None, cache_max_seconds=600, force_update=False):
    """

    :param cache_category: 缓存类别，不同类别的key不冲突
    :param cache_key: 缓存key，单个类别内唯一
    :param cache_miss_func: 缓存未命中时获取最新值的回调，返回值必须要是python原生类型，以便进行json的序列化和反序列化
    :param cache_validate_func: func(cached_value)->bool, 用于检查缓存值是否仍有效，比如如果缓存的是文件路径，则判断路径是否存在
    :param cache_max_seconds: 缓存时限（秒），默认600s
    :return: 缓存中获取的数据（若未过期），或最新获取的数据
    """
    db = CacheDB().with_context(cache_category).load()

    cached_value = ""

    # 尝试使用缓存内容
    if cache_key in db.cache:
        cache_info = db.cache[cache_key]
        cached_value = cache_info.value

        if not force_update:
            if parse_time(cache_info.update_at) + datetime.timedelta(seconds=cache_max_seconds) >= get_now():
                if cache_validate_func is None or cache_validate_func(cache_info.value):
                    logger.debug(f"{cache_category} {cache_key} 本地缓存尚未过期，且检验有效，将使用缓存内容。缓存信息为 {cache_info}")
                    return cache_info.value
        else:
            logger.debug(f"强制更新缓存 cache_category={cache_category} cache_key={cache_key}")

    # 调用回调获取最新结果，并保存
    try:
        latest_value = cache_miss_func()
    except Exception as e:
        logger.error(f"更新缓存时出错了 {cache_category} {cache_key}", exc_info=e)
        # 无法获取最新数据时，则保底使用最后一次缓存的数据
        latest_value = cached_value

    cache_info = CacheInfo()
    cache_info.value = latest_value
    cache_info.update_at = format_now()

    db.cache[cache_key] = cache_info

    db.save()

    return latest_value


def reset_cache(cache_category: str):
    def _reset(db: CacheDB):
        db.cache = {}
        logger.debug(f"清空cache={cache_category}")

    CacheDB().with_context(cache_category).update(_reset)


def count_down(ctx: str, seconds: int, update_interval=0.1):
    if is_run_in_github_action():
        # 在github action环境下直接sleep
        logger.info(f"{ctx} wait for {seconds}seconds")
        time.sleep(seconds)
        return

    now_time = get_now()
    end_time = now_time + datetime.timedelta(seconds=seconds)

    while now_time < end_time:
        remaining_duration = end_time - now_time
        print("\r" + f"{ctx} 剩余等待时间: {remaining_duration}", end='')
        time.sleep(update_interval)
        now_time = get_now()
    print("\r" + " " * 80)


def range_from_one(stop: int):
    return range(1, stop + 1)


def kill_process(pid: int, wait_time=5):
    logger.info(f"尝试干掉原进程={pid}")
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        logger.warning("未找到该pid，也许是早已经杀掉了")

    logger.info(f"等待{wait_time}秒，确保原进程已经被干掉")
    time.sleep(wait_time)


def kill_other_instance_on_start():
    pids_dir = os.path.join(cached_dir, 'pids')
    make_sure_dir_exists(pids_dir)

    old_pids = os.listdir(pids_dir)
    if len(old_pids) != 0:
        logger.info(f"尝试干掉之前的实例: {old_pids}")
        for old_instance_pid in old_pids:
            kill_process(int(old_instance_pid), 1)
            os.remove(os.path.join(pids_dir, old_instance_pid))

    current_pid = os.getpid()
    pid_filename = os.path.join(pids_dir, str(current_pid))
    open(pid_filename, 'w').close()
    logger.info(f"当前pid为{current_pid}")


def append_if_not_in(vlist: list, val: Any) -> list:
    if val not in vlist:
        vlist.append(val)

    return vlist


def wait_for(msg: str, seconds):
    logger.info(msg + f", 等待{seconds}秒")
    time.sleep(seconds)


def show_unexpected_exception_message(e: Exception):
    from config import Config, config

    time_since_release = get_now() - parse_time(ver_time, "%Y.%m.%d")
    cfg = Config()
    try:
        cfg = config()
    except:
        pass
    msg = f"ver {now_version} (发布于{ver_time}，距今已有{time_since_release.days}天啦) 运行过程中出现未捕获的异常，请加群{cfg.common.qq_group}反馈或自行解决。" + check_some_exception(e)
    logger.exception(color("fg_bold_yellow") + msg, exc_info=e)
    logger.warning(color("fg_bold_cyan") + "如果稳定报错，不妨打开网盘，看看是否有新版本修复了这个问题~")
    logger.warning(color("fg_bold_cyan") + "如果稳定报错，不妨打开网盘，看看是否有新版本修复了这个问题~")
    logger.warning(color("fg_bold_cyan") + "如果稳定报错，不妨打开网盘，看看是否有新版本修复了这个问题~")
    logger.warning(color("fg_bold_green") + "如果要反馈，请把整个窗口都截图下来- -不要只截一部分")
    logger.warning(color("fg_bold_yellow") + "不要自动无视上面这三句话哦，写出来是让你看的呀<_<不知道出啥问题的时候就按提示去看看是否有新版本哇，而不是不管三七二十一就来群里问嗷")
    logger.warning(color("fg_bold_cyan") + f"链接：{cfg.common.netdisk_link}")


def get_pay_server_addr() -> str:
    return "http://139.198.179.81:8438"


def disable_quick_edit_mode():
    if not is_windows():
        return

    # https://docs.microsoft.com/en-us/windows/console/setconsolemode
    def _cb():
        ENABLE_EXTENDED_FLAGS = 0x0080

        logger.info(color("bold_green") + "将禁用命令行的快速编辑模式，避免鼠标误触时程序暂停，若需启用，请去配置文件取消禁用快速编辑模式~")
        show_quick_edit_mode_tip()
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(win32api.STD_INPUT_HANDLE), ENABLE_EXTENDED_FLAGS)

    async_call(_cb)


def show_quick_edit_mode_tip():
    logger.info(color("bold_blue") + "当前已禁用快速编辑，如需复制链接，请先按 CTRL+M 临时开启选择功能，然后选择要复制的区域，按 CTRL+C 进行复制\n"
                                     "（如果点击后会退出，也可以点击命令栏左上角图标，编辑->标记，然后选择复制区域来复制即可）")


def is_run_in_pycharm() -> bool:
    return os.getenv('PYCHARM_HOSTED') == '1'


def remove_file(file_path):
    if not os.path.isfile(file_path):
        logger.debug(f"文件 {file_path} 不存在")
        return

    try:
        os.remove(file_path)
    except Exception as e:
        logger.error(f"删除文件 {file_path} 失败", exc_info=e)


def remove_directory(directory_path):
    if not os.path.isdir(directory_path):
        logger.debug(f"目录 {directory_path} 不存在")
        return

    try:
        shutil.rmtree(directory_path)
    except Exception as e:
        logger.error(f"删除目录 {directory_path} 失败", exc_info=e)


def wait_a_while(idx: int):
    # 各进程按顺序依次等待对应时长，避免多个进程输出混在一起
    time.sleep(0.1 * idx)


def md5(val: str) -> str:
    return hashlib.md5(val.encode()).hexdigest()


def md5_file(filepath: str) -> str:
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


# 以下函数必定不是我们感兴趣的调用处
ignore_caller_names = {
    'process_result',
    'get',
    'post',
    'amesvr_request',
    'check_bind_account',
    'is_guanjia_openid_expired',
    'fetch_guanjia_openid',
    'wrapper',
    'show_head_line',
    'show_ams_act_info',
    'show_amesvr_act_info',
    'show_not_ams_act_info',
    'query_dnf_rolelist',
    'temporary_change_bind_and_do',
    'try_do_with_lucky_role_and_normal_role',
    'try_request',
}

ignore_prefixes = [
    'check_',
    'do_',
    'query_',
    '_',
]
ignore_suffixes = [
    '_op',
]


def get_meaningful_call_point_for_log() -> str:
    """
    获取实际有意义的调用处，比如这个日志是在通用的回包处记录的，默认会打印回包的地方，但我们实际感兴趣的是外部调用这个请求的地方
    """
    # 获取除自身外的其他调用处
    stack_except_this = inspect.stack()[1:]

    for caller_info in stack_except_this:
        if caller_info.function in ignore_caller_names \
                or startswith_any(caller_info.function, ignore_prefixes) \
                or endswith_any(caller_info.function, ignore_suffixes):
            continue

        call_at = f"{caller_info.function}:{caller_info.lineno} "
        return call_at

    return ""


def startswith_any(string: str, prefixes: List[str]) -> bool:
    for prefix in prefixes:
        if string.startswith(prefix):
            return True

    return False


def endswith_any(string: str, suffixes: List[str]) -> bool:
    for suffix in suffixes:
        if string.endswith(suffix):
            return True

    return False


def extract_between(html: str, prefix: str, suffix: str, typ: Type) -> Any:
    prefix_idx = html.index(prefix) + len(prefix)
    suffix_idx = html.index(suffix, prefix_idx)

    return typ(html[prefix_idx:suffix_idx])


def popen(args, cwd="."):
    if type(args) is list:
        args = [str(arg) for arg in args]

    if is_windows():
        subprocess.Popen(args, cwd=cwd, shell=True, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    else:
        subprocess.Popen(args, cwd=cwd, shell=True,
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def start_djc_helper(exe_path: str):
    popen([
        exe_path,
        "--wait_for_pid_exit", os.getpid(),
        "--max_wait_time", 5,
    ])
    logger.info(f"{exe_path} 已经启动~")


def sync_configs(source_dir: str, target_dir: str):
    """
    将指定的配置相关文件从 源目录 覆盖到 目标目录
    """
    sync_config_list = [
        # 配置文件
        "config.toml",
        "config.toml.local",

        # 特定功能的开关
        ".disable_pause_after_run",
        ".use_by_myself",
        "不查询活动.txt",
        ".no_message_box",

        # 缓存文件所在目录
        ".db",

        # # 自动更新DLC
        # "utils/auto_updater.exe"
    ]

    logger.debug(f"将以下配置从{source_dir} 复制并覆盖到 {target_dir}")

    for filename in sync_config_list:
        source = os.path.join(source_dir, filename)
        destination = os.path.join(target_dir, filename)

        if not os.path.exists(source):
            logger.debug(f"旧版本目录未发现 {filename}，将跳过")
            continue

        if 'config.toml' in filename and os.stat(source).st_size == 0:
            logger.warning(f"旧版本中的配置文件是空文件，可能意外损坏了，将不覆盖到本地")
            continue

        # 确保要复制的目标文件所在目录存在
        make_sure_dir_exists(os.path.dirname(destination))

        if os.path.isdir(filename):
            logger.debug(f"覆盖目录 {filename}")
            remove_directory(destination)
            shutil.copytree(source, destination)
        else:
            logger.debug(f"覆盖文件 {filename}")
            remove_file(destination)
            shutil.copyfile(source, destination)


def start_and_end_date_of_a_month(date: datetime.datetime) -> Tuple[datetime.datetime, datetime.datetime]:
    """
    返回对应时间所在月的起始和结束时间点，形如 2021-07-01 00:00:00 和 2021-07-31 23:59:59
    """
    this_mon_start_date = date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    month = this_mon_start_date.month
    year = this_mon_start_date.year
    if month == 12:
        month = 1
        year += 1
    else:
        month += 1
    next_month_start_date = this_mon_start_date.replace(month=month, year=year)

    this_month_end_date = (next_month_start_date - datetime.timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=0)

    return this_mon_start_date, this_month_end_date


# 常见系统变量：https://docs.microsoft.com/en-us/windows/deployment/usmt/usmt-recognized-environment-variables

def get_appdata_dir() -> str:
    if is_windows():
        return os.path.expandvars("%APPDATA%")
    else:
        return os.path.expandvars("$HOME/AppData")


def get_user_dir() -> str:
    if is_windows():
        return os.path.expandvars("%USERPROFILE%")
    else:
        return os.path.expandvars("$HOME")


def get_path_in_onedrive(relative_path: str) -> str:
    return os.path.realpath(os.path.join(get_user_dir(), "OneDrive", relative_path))


def change_title(dlc_info="", monthly_pay_info="", multiprocessing_pool_size=0, enable_super_fast_mode=False):
    if dlc_info == "" and exists_auto_updater_dlc():
        dlc_info = " 自动更新豪华升级版"

    pool_info = ""
    if multiprocessing_pool_size != 0:
        pool_info = f"火力全开版本({multiprocessing_pool_size})"
        if enable_super_fast_mode:
            pool_info = "超级" + pool_info

    set_title_cmd = f"title DNF蚊子腿小助手 {dlc_info} {monthly_pay_info} {pool_info} v{now_version} by风之凌殇 {get_random_face()}"
    if is_windows():
        os.system(set_title_cmd)
    else:
        logger.info(color("bold_yellow") + set_title_cmd)


def exists_auto_updater_dlc():
    return os.path.isfile(auto_updater_path())


def auto_updater_path():
    return os.path.realpath("utils/auto_updater.exe")


def auto_updater_latest_path():
    return os.path.realpath("utils/auto_updater_latest.exe")


def remove_suffix(input_string: str, suffix: str) -> str:
    if suffix and input_string.endswith(suffix):
        return input_string[:-len(suffix)]
    return input_string


def get_cid():
    return "{}-{}".format(platform.node(), uuid.getnode())


def get_resolution() -> str:
    width, height = get_screen_size()
    return f"{width}x{height}"


def bypass_proxy():
    os.environ['no_proxy'] = '*'


def use_proxy():
    if 'no_proxy' not in os.environ:
        return

    os.environ.pop('no_proxy')


def parse_scode(scode_or_url: str) -> str:
    if "dnf.qq.com" not in scode_or_url:
        # 是scode
        return scode_or_url
    else:
        # 是url
        # https://dnf.qq.com/cp/a20210730care/index.html?sCode=MDJKQ0t5dDJYazlMVmMrc2ZXV0tVT0xsZitZMi9YOXZUUFgxMW1PcnQ2Yz0=
        parsed = parse.urlparse(scode_or_url)
        return parse.parse_qs(parsed.query)['sCode'][0]


def pause():
    if is_windows():
        pause_cmd = 'PAUSE'
    else:
        pause_cmd = 'read -r -p "Press Enter to continue..." key'
    os.system(pause_cmd)


def bytes_arr_to_hex_str(bytes_arr: List[int]) -> str:
    """
    [0x58, 0x59, 0x01, 0x00, 0x00] => "0x58, 0x59, 0x01, 0x00, 0x00"
    """
    return ", ".join("0x%02x" % b for b in bytes_arr)


def hex_str_to_bytes_arr(bytes_str: str) -> List[int]:
    """
    "0x58, 0x59, 0x01, 0x00, 0x00" => [0x58, 0x59, 0x01, 0x00, 0x00]
    """
    return eval(f"[{bytes_str}]")


def utf8len(s: str) -> int:
    return len(s.encode('utf-8'))


def base64_str(text: str) -> str:
    return base64.standard_b64encode(text.encode()).decode()


def json_compact(val) -> str:
    return json.dumps(val, separators=(',', ':'))


if __name__ == '__main__':
    # print(get_now_unix())
    # print(get_this_week_monday())
    # print(get_last_week_monday())
    # print(get_uuid())
    # print(run_from_src())
    # print(use_by_myself())
    # print(show_end_time("2021-02-23 00:00:00"))
    # print(truncate("风之凌殇风之凌殇", 12))
    # print(parse_time("2021-02-10 18:55:35") + datetime.timedelta(days=10 * 31))
    # print(remove_none_from_list([None, 1, 2, 3, None]))
    # print(get_screen_size())
    # kill_other_instance_on_start()
    # print(md5(""))

    # test_extract_between()

    # print(start_and_end_date_of_a_month(get_now()))

    clear_login_status()

    pass
