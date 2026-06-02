
import re

with open('code/效率测算/20_碳排放效率绘图.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. MAP_PATH
content = content.replace(
    'MAP_PATH = resolve_project_path(CONFIG["map_geojson"])',
    'MAP_PATH = PROJECT_ROOT / "data" / "外部资料" / "中国_省.geojson"')

# 2. Add iter_line_strings
old = '    return polygons\n\n\ndef save_year_mean_plot'
new = '    return polygons\n\n\ndef iter_line_strings(geometry: dict) -> list[list[tuple[float, float]]]:\n    gtype = geometry.get("type")\n    coords = geometry.get("coordinates", [])\n    lines: list[list[tuple[float, float]]] = []\n    if gtype == "LineString":\n        if coords:\n            lines.append([(x, y) for x, y in coords])\n    elif gtype == "MultiLineString":\n        for line in coords:\n            if line:\n                lines.append([(x, y) for x, y in line])\n    return lines\n\n\ndef save_year_mean_plot'
content = content.replace(old, new)

with open('code/效率测算/20_碳排放效率绘图.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Step 1 done: MAP_PATH + iter_line_strings')
