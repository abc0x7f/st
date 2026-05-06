from __future__ import annotations

import csv
from collections import OrderedDict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INPUT_PATH = ROOT / "data" / "中间数据" / "碳排放效率结果_2015_2022.csv"
ECONOMIC_INPUT_PATH = ROOT / "data" / "最终数据" / "第一阶段_基础.csv"
ADJ_OUTPUT_PATH = ROOT / "data" / "最终数据" / "省际01邻接矩阵.csv"
ECONOMIC_OUTPUT_PATH = ROOT / "data" / "最终数据" / "省际经济距离矩阵.csv"


def load_province_order(path: Path) -> list[str]:
    seen: OrderedDict[str, None] = OrderedDict()
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            province = row["province"].strip()
            if province not in seen:
                seen[province] = None
    return list(seen.keys())


def build_adjacency_pairs() -> dict[str, set[str]]:
    # 基准按省级陆地接壤关系构造；按用户要求，额外加入“海南-广东”的人为连接。
    pairs = {
        "上海": {"江苏", "浙江"},
        "云南": {"四川", "贵州", "广西"},
        "内蒙古": {"北京", "河北", "山西", "陕西", "宁夏", "甘肃", "辽宁", "吉林", "黑龙江"},
        "北京": {"内蒙古", "河北", "天津"},
        "吉林": {"内蒙古", "辽宁", "黑龙江"},
        "四川": {"云南", "贵州", "重庆", "陕西", "甘肃", "青海"},
        "天津": {"北京", "河北"},
        "宁夏": {"内蒙古", "甘肃", "陕西"},
        "安徽": {"江苏", "浙江", "江西", "湖北", "河南", "山东"},
        "山东": {"河北", "河南", "安徽", "江苏"},
        "山西": {"内蒙古", "河北", "河南", "陕西"},
        "广东": {"福建", "江西", "湖南", "广西", "海南"},
        "广西": {"云南", "贵州", "湖南", "广东"},
        "新疆": {"甘肃", "青海"},
        "江苏": {"上海", "浙江", "安徽", "山东"},
        "江西": {"浙江", "安徽", "湖北", "湖南", "广东", "福建"},
        "河北": {"辽宁", "内蒙古", "山西", "河南", "山东", "北京", "天津"},
        "河南": {"河北", "山西", "陕西", "湖北", "安徽", "山东"},
        "浙江": {"上海", "江苏", "安徽", "江西", "福建"},
        "海南": {"广东"},
        "湖北": {"河南", "安徽", "江西", "湖南", "重庆", "陕西"},
        "湖南": {"湖北", "江西", "广东", "广西", "贵州", "重庆"},
        "甘肃": {"新疆", "青海", "四川", "陕西", "宁夏", "内蒙古"},
        "福建": {"浙江", "江西", "广东"},
        "贵州": {"云南", "四川", "重庆", "湖南", "广西"},
        "辽宁": {"河北", "内蒙古", "吉林"},
        "重庆": {"四川", "贵州", "湖南", "湖北", "陕西"},
        "陕西": {"内蒙古", "山西", "河南", "湖北", "重庆", "四川", "甘肃", "宁夏"},
        "青海": {"新疆", "甘肃", "四川"},
        "黑龙江": {"内蒙古", "吉林"},
    }

    # 强制对称，避免单边遗漏。
    symmetric: dict[str, set[str]] = {k: set(v) for k, v in pairs.items()}
    for province, neighbors in pairs.items():
        for neighbor in neighbors:
            symmetric.setdefault(neighbor, set()).add(province)
    return symmetric


def write_matrix(provinces: list[str], adjacency: dict[str, set[str]], path: Path) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["province", *provinces])
        for province in provinces:
            row = [province]
            neighbors = adjacency.get(province, set())
            for other in provinces:
                value = 1 if other in neighbors and other != province else 0
                row.append(value)
            writer.writerow(row)


def load_average_gdp(path: Path, provinces: list[str]) -> dict[str, float]:
    gdp_by_province: dict[str, list[float]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"province", "GDP_constant"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path.name} 缺少字段: {sorted(missing)}")

        for row in reader:
            province = row["province"].strip()
            if province not in provinces:
                continue

            raw_value = row["GDP_constant"].strip()
            if not raw_value:
                continue

            value = float(raw_value)
            gdp_by_province.setdefault(province, []).append(value)

    missing = [province for province in provinces if province not in gdp_by_province]
    if missing:
        raise ValueError(f"未在经济数据中找到这些省份: {missing}")

    return {
        province: sum(values) / len(values)
        for province, values in gdp_by_province.items()
    }


def write_economic_distance_matrix(
    provinces: list[str],
    avg_gdp: dict[str, float],
    path: Path,
) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["province", *provinces])
        for province in provinces:
            base_gdp = avg_gdp[province]
            row = [province]
            for other in provinces:
                if other == province:
                    row.append(0.0)
                    continue

                distance = abs(base_gdp - avg_gdp[other])
                value = 0.0 if distance == 0 else 1.0 / distance
                row.append(value)
            writer.writerow(row)


def main() -> None:
    provinces = load_province_order(INPUT_PATH)
    adjacency = build_adjacency_pairs()
    avg_gdp = load_average_gdp(ECONOMIC_INPUT_PATH, provinces)

    missing = [province for province in provinces if province not in adjacency]
    if missing:
        raise ValueError(f"未在邻接字典中找到这些省份: {missing}")

    write_matrix(provinces, adjacency, ADJ_OUTPUT_PATH)
    write_economic_distance_matrix(provinces, avg_gdp, ECONOMIC_OUTPUT_PATH)
    print(f"saved: {ADJ_OUTPUT_PATH}")
    print(f"saved: {ECONOMIC_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
