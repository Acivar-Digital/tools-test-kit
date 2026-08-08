import re

with open("src2/engine/module12_compatibility.py") as f:
    content = f.read()

# I will write a simple regex replacement to remove GE_JU_COMPATIBILITY completely
# and replace _get_ge_ju_score logic

new_ge_ju_score = """
def _get_ge_ju_score(struct1: str | None, struct2: str | None) -> tuple[float, str]:
    if not struct1 or not struct2:
        return 50.0, "Neutral base (structures unknown)"

    s1 = struct1.lower().strip()
    s2 = struct2.lower().strip()

    # helper for fast match
    def _score(norm1: str, norm2: str) -> tuple[float, str]:
        match norm1:
            case "zheng_guan_ge":
                match norm2:
                    case "zheng_guan_ge" | "zheng_yin_ge" | "zheng_cai_ge" | "pian_cai_ge" | "shi_shen_ge": return 85.0, "Excellent structure harmony"
                    case "qi_sha_ge" | "yin_xiao_ge" | "shang_guan_ge": return 30.0, "Challenging structure harmony"
                    case _: return 65.0, "Good structure harmony"
            case "qi_sha_ge":
                match norm2:
                    case "yin_xiao_ge" | "yang_ren_ge" | "shi_shen_ge": return 85.0, "Excellent structure harmony"
                    case "zheng_guan_ge" | "zheng_yin_ge" | "zheng_cai_ge": return 30.0, "Challenging structure harmony"
                    case _: return 65.0, "Good structure harmony"
            case "yin_xiao_ge":
                match norm2:
                    case "qi_sha_ge" | "yang_ren_ge" | "shi_shen_ge": return 85.0, "Excellent structure harmony"
                    case "zheng_guan_ge" | "zheng_yin_ge" | "zheng_cai_ge": return 30.0, "Challenging structure harmony"
                    case _: return 65.0, "Good structure harmony"
            case "cai_ge" | "zheng_cai_ge" | "pian_cai_ge":
                match norm2:
                    case "zheng_guan_ge" | "qi_sha_ge" | "shi_shen_ge" | "shang_guan_ge": return 85.0, "Excellent structure harmony"
                    case "bi_jian_ge" | "jie_cai_ge" | "yang_ren_ge": return 30.0, "Challenging structure harmony"
                    case _: return 65.0, "Good structure harmony"
            case "shi_shen_ge":
                match norm2:
                    case "zheng_guan_ge" | "zheng_cai_ge" | "pian_cai_ge" | "bi_jian_ge": return 85.0, "Excellent structure harmony"
                    case "yin_xiao_ge" | "pian_yin_ge": return 30.0, "Challenging structure harmony"
                    case _: return 65.0, "Good structure harmony"
            case "shang_guan_ge":
                match norm2:
                    case "zheng_cai_ge" | "pian_cai_ge" | "yin_xiao_ge": return 85.0, "Excellent structure harmony"
                    case "zheng_guan_ge" | "qi_sha_ge": return 30.0, "Challenging structure harmony"
                    case _: return 65.0, "Good structure harmony"
            case "jian_lu_ge":
                match norm2:
                    case "zheng_guan_ge" | "zheng_cai_ge" | "pian_cai_ge" | "shi_shen_ge": return 85.0, "Excellent structure harmony"
                    case "qi_sha_ge" | "yin_xiao_ge": return 30.0, "Challenging structure harmony"
                    case _: return 65.0, "Good structure harmony"
            case "yang_ren_ge":
                match norm2:
                    case "qi_sha_ge" | "yin_xiao_ge" | "shang_guan_ge": return 85.0, "Excellent structure harmony"
                    case "zheng_guan_ge" | "zheng_cai_ge" | "pian_cai_ge": return 30.0, "Challenging structure harmony"
                    case _: return 65.0, "Good structure harmony"
            case _:
                return 50.0, "Neutral structure harmony"

    # Symmetric scoring (take average)
    sc1, desc1 = _score(s1, s2)
    sc2, desc2 = _score(s2, s1)
    final_score = (sc1 + sc2) / 2.0

    return final_score, desc1
"""

# Replace the giant dict and _get_ge_ju_score
content = re.sub(r'GE_JU_COMPATIBILITY = \{.*?\n\}\n', '', content, flags=re.DOTALL)
content = re.sub(r'def _get_ge_ju_score.*?return score, desc\n', new_ge_ju_score, content, flags=re.DOTALL)

with open("src2/engine/module12_compatibility.py", "w") as f:
    f.write(content)
