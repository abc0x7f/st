from __future__ import annotations

import json
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

import geopandas as gpd
import pandas as pd


PROJECT_ROOT = Path(r"C:\Users\abc0x7f\Desktop\PRO\统计建模")
PROVINCE_GEOJSON = PROJECT_ROOT / "data/外部资料/中国省级地图.geojson"
CITY_GEOJSON = PROJECT_ROOT / "data/外部资料/中国市级地图.geojson"
PANEL_FILE = PROJECT_ROOT / "data/最终数据/第二阶段_基础.csv"
ECONOMIC_MATRIX_FILE = PROJECT_ROOT / "data/最终数据/省际经济距离矩阵.csv"

OUT_CAPITALS = PROJECT_ROOT / "data/中间数据/省会城市坐标表.csv"
OUT_MATRIX = PROJECT_ROOT / "data/最终数据/省际地理距离倒数矩阵_省会版.csv"
OUT_NESTED_MATRIX = PROJECT_ROOT / "data/最终数据/省际经济地理嵌套矩阵_省会版.csv"


CAPITAL_MAP = {
    "上海": ("province", "上海市"),
    "云南": ("city", "昆明市"),
    "内蒙古": ("city", "呼和浩特市"),
    "北京": ("province", "北京市"),
    "吉林": ("city", "长春市"),
    "四川": ("city", "成都市"),
    "天津": ("province", "天津市"),
    "宁夏": ("city", "银川市"),
    "安徽": ("city", "合肥市"),
    "山东": ("city", "济南市"),
    "山西": ("city", "太原市"),
    "广东": ("city", "广州市"),
    "广西": ("city", "南宁市"),
    "新疆": ("city", "乌鲁木齐市"),
    "江苏": ("city", "南京市"),
    "江西": ("city", "南昌市"),
    "河北": ("city", "石家庄市"),
    "河南": ("city", "郑州市"),
    "浙江": ("city", "杭州市"),
    "海南": ("city", "海口市"),
    "湖北": ("city", "武汉市"),
    "湖南": ("city", "长沙市"),
    "甘肃": ("city", "兰州市"),
    "福建": ("city", "福州市"),
    "贵州": ("city", "贵阳市"),
    "辽宁": ("city", "沈阳市"),
    "重庆": ("province", "重庆市"),
    "陕西": ("city", "西安市"),
    "青海": ("city", "西宁市"),
    "黑龙江": ("city", "哈尔滨市"),
}


def parse_point(value: object) -> tuple[float, float]:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return float(value[0]), float(value[1])
    if hasattr(value, "__len__") and hasattr(value, "__getitem__") and not isinstance(value, (str, bytes)):
        if len(value) >= 2:
            return float(value[0]), float(value[1])
    if isinstance(value, str):
        parsed = json.loads(value)
        return float(parsed[0]), float(parsed[1])
    raise ValueError(f"Unsupported point value: {value!r}")


def haversine_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return 6371.0 * c


def load_required_provinces() -> list[str]:
    df = pd.read_csv(PANEL_FILE, encoding="utf-8")
    provinces = sorted(df["province"].dropna().astype(str).str.strip().unique().tolist())
    return provinces


def build_capital_table() -> pd.DataFrame:
    provinces = load_required_provinces()
    province_gdf = gpd.read_file(PROVINCE_GEOJSON)
    city_gdf = gpd.read_file(CITY_GEOJSON)

    rows: list[dict[str, object]] = []
    for province in provinces:
        source_level, source_name = CAPITAL_MAP[province]
        if source_level == "city":
            source = city_gdf[(city_gdf["level"] == "city") & (city_gdf["name"] == source_name)]
        else:
            source = province_gdf[province_gdf["name"] == source_name]

        if source.empty:
            raise ValueError(f"Cannot find source feature for {province} -> {source_name}")

        record = source.iloc[0]
        center_lon, center_lat = parse_point(record["center"])
        centroid_lon, centroid_lat = parse_point(record["centroid"])
        rows.append(
            {
                "province": province,
                "capital": source_name,
                "source_level": source_level,
                "source_name": source_name,
                "adcode": record["adcode"],
                "center_lon": center_lon,
                "center_lat": center_lat,
                "centroid_lon": centroid_lon,
                "centroid_lat": centroid_lat,
            }
        )

    df = pd.DataFrame(rows)
    order = pd.Categorical(df["province"], categories=provinces, ordered=True)
    return df.sort_values("province", key=lambda s: order).reset_index(drop=True)


def build_inverse_distance_matrix(capitals: pd.DataFrame) -> pd.DataFrame:
    provinces = capitals["province"].tolist()
    lon = capitals["center_lon"].tolist()
    lat = capitals["center_lat"].tolist()

    matrix = []
    for i, province_i in enumerate(provinces):
        row = {"province": province_i}
        for j, province_j in enumerate(provinces):
            if i == j:
                row[province_j] = 0.0
            else:
                dist = haversine_km(lon[i], lat[i], lon[j], lat[j])
                row[province_j] = 0.0 if dist == 0 else 1.0 / dist
        matrix.append(row)
    return pd.DataFrame(matrix)


def align_matrix(df: pd.DataFrame, provinces: list[str]) -> pd.DataFrame:
    matrix = df.copy()
    matrix["province"] = matrix["province"].astype(str).str.strip()
    matrix = matrix.set_index("province")
    matrix.columns = [str(col).strip() for col in matrix.columns]
    matrix = matrix.loc[provinces, provinces]
    matrix = matrix.apply(pd.to_numeric, errors="coerce")
    matrix.insert(0, "province", matrix.index)
    return matrix.reset_index(drop=True)


def build_nested_matrix(geo_matrix: pd.DataFrame, provinces: list[str]) -> pd.DataFrame:
    economic = pd.read_csv(ECONOMIC_MATRIX_FILE, encoding="utf-8")
    economic = align_matrix(economic, provinces)
    geo = align_matrix(geo_matrix, provinces)

    nested = geo.copy()
    for province in provinces:
        nested[province] = 0.5 * geo[province] + 0.5 * economic[province]
    return nested


def main() -> None:
    OUT_CAPITALS.parent.mkdir(parents=True, exist_ok=True)
    OUT_MATRIX.parent.mkdir(parents=True, exist_ok=True)
    OUT_NESTED_MATRIX.parent.mkdir(parents=True, exist_ok=True)

    capitals = build_capital_table()
    capitals.to_csv(OUT_CAPITALS, index=False, encoding="utf-8-sig")

    provinces = capitals["province"].tolist()
    matrix = build_inverse_distance_matrix(capitals)
    matrix = align_matrix(matrix, provinces)
    matrix.to_csv(OUT_MATRIX, index=False, encoding="utf-8-sig")

    nested_matrix = build_nested_matrix(matrix, provinces)
    nested_matrix.to_csv(OUT_NESTED_MATRIX, index=False, encoding="utf-8-sig")

    print(f"Saved capitals: {OUT_CAPITALS}")
    print(f"Saved matrix:   {OUT_MATRIX}")
    print(f"Saved nested:   {OUT_NESTED_MATRIX}")


if __name__ == "__main__":
    main()
