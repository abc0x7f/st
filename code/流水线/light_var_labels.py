from __future__ import annotations

from pathlib import Path


PRE_LOG_LIGHT_LABEL = "夜间灯光强度（取对数前）"
LOG_LIGHT_LABEL = "夜间灯光强度"


def _data_file_name(data_file: str | Path | None) -> str:
    if data_file is None:
        return ""
    return Path(str(data_file)).name


def light_var_label(var_name: str, data_file: str | Path | None = None) -> str:
    file_name = _data_file_name(data_file)

    if var_name == "ntl":
        return PRE_LOG_LIGHT_LABEL
    if var_name == "lntl":
        if file_name == "第二阶段_ntl对照.csv":
            return PRE_LOG_LIGHT_LABEL
        return LOG_LIGHT_LABEL
    if var_name == "lntl_1":
        if file_name == "第二阶段_基础.csv":
            return "滞后一期夜间灯光强度"
        if file_name == "第二阶段_滞后一期.csv":
            return "当期夜间灯光强度"
        if file_name == "第二阶段_ntl对照.csv":
            return "夜间灯光强度（对数后）"
        return "对照夜间灯光强度"
    return var_name
