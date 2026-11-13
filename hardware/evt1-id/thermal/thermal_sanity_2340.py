#!/usr/bin/env python3
# 独立对照 Claude 23:40 手算，非原始 Claude 源码，也不是热仿真/实测。
# 单区域自然对流玩具模型 T = Tamb + P/(h*A)。不考虑热导/皮肤/辐射/日照。
import json
ambient=25.0; h=10.0
area_assumed=0.0072
# 几何上限: 镜腿 145 mm 长，6.5 mm×11.5 mm 矩形周长; 全表面均有效也仅为这个数量级。
area_temple_perimeter=2*(6.5+11.5)*145/1_000_000
result={"method":"T=Tamb+P/(h*A) pure sanity check", "not_measurement":True,
        "h_assumed_W_per_m2K":h,"ambient_C":ambient,
        "Claude_effective_area_m2":area_assumed,
        "temple_gross_all_faces_area_m2":round(area_temple_perimeter,6),
        "effective_area_exceeds_single_temple_gross_area":area_assumed>area_temple_perimeter,
        "HUD_0.65W_C_using_Claude_area":round(ambient+.65/(h*area_assumed),2),
        "CAPTURE_1.25W_C_using_Claude_area":round(ambient+1.25/(h*area_assumed),2),
        "HUD_0.65W_C_gross_temple_area_upper_bound":round(ambient+.65/(h*area_temple_perimeter),2),
        "CAPTURE_1.25W_C_gross_temple_area_upper_bound":round(ambient+1.25/(h*area_temple_perimeter),2)}
print(json.dumps(result,ensure_ascii=False,indent=2))
