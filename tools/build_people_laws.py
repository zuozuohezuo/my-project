"""Rebuild the manually researched history catalogue from checked source anchors.

These records are research data, not simulated personality scores or game effects.
Run the download script first. Evidence anchors must exist in the saved body text.
"""
from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "data/history"


def evidence(source_id, locator, anchor, length=140):
    raw = (DEST / "raw" / f"{source_id}.txt").read_text(encoding="utf-8")
    compact = re.sub(r"\s+", "", raw)
    key = re.sub(r"\s+", "", anchor)
    index = compact.find(key)
    if index < 0:
        raise ValueError(f"Source anchor not found: {source_id}: {anchor}")
    return {"source_id": source_id, "locator": locator,
            "anchor": anchor, "excerpt": compact[index:index + length],
            "evidence_kind": "原典文字（空白已规范化；完整上下文见正文及HTML）"}


def write(name, records, note):
    payload = {"metadata": {"schema_version": 1, "baseline_year": 1500,
               "baseline_era": "弘治十三年", "baseline_month": 1,
               "calendar_note": "明代农历；不把正月等同公历1月；未实现闰月。",
               "baseline_is_provisional": True, "coverage_note": note,
               "simulation_effects_enabled": False}, "records": records}
    (DEST / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def person(pid, name, offices, roles, note, evidence_items, later=None, titles=None):
    return {"id": pid, "name": name, "office_ids": offices, "roles": roles,
            "period": "弘治十三年（1500）正月工作快照",
            "time_applicability": {"snapshot_year": 1500, "snapshot_lunar_month": 1,
                                   "role_at_snapshot": roles, "later_changes": later or [],
                                   "later_changes_are_reference_only": True},
            "titular_titles": titles or [], "note": note,
            "source_ids": list(dict.fromkeys(e["source_id"] for e in evidence_items)),
            "verification_status": "纪年与任职条目已核对（非完整履历校勘）",
            "fact_kind": "史料记载及明确标注的开局时间归纳",
            "personality_scores": None, "evidence": evidence_items}


def build_people():
    e = evidence
    records = [
      person("ming_person_zhu_youtang", "朱祐樘", ["ming_office_emperor"], ["皇帝（明孝宗）"],
             "弘治皇帝；本纪记成化二十三年九月即位。健康、行动力、性格及忠心数值不从史料直接推定。",
             [e("mingshi_015", "孝宗本纪开篇及成化二十三年", "孝宗建天明道"),
              e("mingshi_015", "弘治十三年正月", "十三年春正月乙丑")]),
      person("ming_person_liu_jian", "刘健", ["ming_office_grand_secretary"], ["内阁首辅", "谨身殿大学士"],
             "1498年徐溥退休后居首辅。户部尚书是阁臣兼衔，不能与实际掌部的周经合并为同一岗位。",
             [e("mingshi_109", "弘治十一至十三年宰辅", "健二月加少傅兼太子太傅戶部尚書謹身殿大學士"),
              e("mingshi_181", "刘健传", "十一年春，進少傅兼太子太傅"),
              e("mingshi_015", "弘治十三年五月", "召大學士劉健、李東陽、謝遷於平臺")],
             titles=["少傅兼太子太傅", "户部尚书（阁臣兼衔）"]),
      person("ming_person_li_dongyang", "李东阳", ["ming_office_grand_secretary"], ["内阁大学士", "文渊阁大学士"],
             "弘治八年入阁；1503年的谨身殿大学士等后加衔不提前写入1500年。",
             [e("mingshi_109", "弘治十一至十三年宰辅", "東陽二月晉太子少保禮部尚書兼文淵閣大學士"),
              e("mingshi_015", "弘治八年二月", "禮部侍郎李東陽、少詹事謝遷入閣")],
             titles=["太子少保", "礼部尚书（阁臣兼衔）"]),
      person("ming_person_xie_qian", "谢迁", ["ming_office_grand_secretary"], ["内阁大学士", "东阁大学士"],
             "弘治八年入阁；兵部尚书是阁臣兼衔，不替代实际掌部的马文升。",
             [e("mingshi_109", "弘治十一至十三年宰辅", "遷二月晉太子少保兵部尚書兼東閣大學士"),
              e("mingshi_015", "弘治十三年五月", "召大學士劉健、李東陽、謝遷於平臺")],
             titles=["太子少保", "兵部尚书（阁臣兼衔）"]),
    ]
    # The May retirement notices attest who held these posts immediately beforehand.
    departures = [
      ("tu_yong", "屠滽", "personnel", "吏部尚书", "滽五月加柱國，致仕", "吏部尚书屠滽", "六月由倪岳继任"),
      ("zhou_jing", "周经", "revenue", "户部尚书", "經五月晉太子太保，致仕", "户部尚书周经", "五月由佀钟继任"),
      ("xu_qiong", "徐琼", "rites", "礼部尚书", "瓊五月晉太子太保，致仕", "礼部尚书徐琼", "五月由傅瀚继任"),
      ("bai_ang", "白昂", "justice", "刑部尚书", "昂五月加太子太傅，致仕", "刑部尚书白昂", "五月由闵珪继任"),
      ("xu_guan", "徐贯", "works", "工部尚书", "貫五月加太子太傅，致仕", "工部尚书徐贯", "五月由曾鉴继任"),
    ]
    for pid, name, department, role, table_anchor, chrono_anchor, successor in departures:
        items = [e("mingshi_111", "弘治十二、十三年七卿表，对照同表列标题", table_anchor),
                 e("mingtongjian_043", "弘治十三年五月五部尚书致仕", chrono_anchor)]
        if pid == "zhou_jing":
            items.append(e("mingshi_183", "周经传", "明年，代葉淇為戶部尚書"))
        records.append(person(f"ming_person_{pid}", name, [f"ming_office_{department}_minister"], [role],
                       f"由弘治十二年年表连续任职与十三年五月离任记载归纳正月在任；{successor}。此后史实变动仅供查阅，游戏不会强制重演。",
                       items, later=[{"year": 1500, "lunar_month": 5, "change": f"致仕；{successor}"}]))
    records.append(person("ming_person_ma_wensheng", "马文升", ["ming_office_war_minister"], ["兵部尚书"],
        "弘治二年任兵部尚书兼督团营；1500年仍掌兵部。1501年十月改吏部，不能提前设为吏部尚书。",
        [e("mingshi_111", "弘治二年七卿表", "馬文升二月任，兼督團營"),
         e("mingtongjian_043", "弘治十三年六月", "兵部非文升不可")],
        later=[{"year": 1500, "lunar_month": 6, "change": "加少傅，仍掌兵部"},
               {"year": 1501, "lunar_month": 10, "change": "改吏部尚书"}]))
    records.append(person("ming_person_min_gui", "闵珪", ["ming_office_censor_left"], ["左都御史"],
        "1500正月为左都御史；五月才改刑部尚书。姓名采用珪，保留常见异写闵圭作检索别名。",
        [e("mingshi_111", "弘治十三年七卿表", "珪五月遷刑部尚書"),
         e("mingtongjian_043", "弘治十三年五月", "左都御史闵珪为刑部尚书"),
         e("mingshi_183", "闵珪传", "十三年代白昂為刑部尚書")],
        later=[{"year": 1500, "lunar_month": 5, "change": "改刑部尚书"}]))
    records[-1]["aliases"] = ["闵圭", "閔珪"]
    records.append(person("ming_person_si_zhong", "佀钟", ["ming_office_censor_right"], ["右都御史"],
        "1500正月为右都御史，五月改户部尚书。在线卷185正文出现似鐘/侶鐘等异写；以篇目、年表及《明通鉴》互核为佀钟，异文仍待影印本校勘。",
        [e("mingshi_111", "弘治十一至十三年七卿表", "鍾十二月任右"),
         e("mingtongjian_043", "弘治十三年五月", "右都御史佀钟为户部尚书")],
        later=[{"year": 1500, "lunar_month": 5, "change": "改户部尚书"}]))
    records[-1]["aliases"] = ["佀鍾", "似鐘", "侶鐘"]
    records[-1]["verification_status"] = "任职互核；姓名录文异体待影印本复校"
    records.append(person("ming_person_dai_shan", "戴珊", ["ming_office_nanjing_justice_minister"], ["南京刑部尚书"],
        "开局在南京，不是1500正月的北京左都御史；当年六月才调任左都御史。",
        [e("mingshi_183", "戴珊传", "進南京刑部尚書。久之，召為左都御史"),
         e("mingshi_111", "弘治十三年六月", "戴珊六月任左"),
         e("mingtongjian_043", "弘治十三年六月", "召南京刑部尚书戴珊为左都御史")],
        later=[{"year": 1500, "lunar_month": 6, "change": "调左都御史"}]))
    write("people.json", records, "13名皇帝、阁臣及中央主要官员的工作快照；不含全国地方官完整名册，未编造能力性格健康评分。")


def build_offices():
    records = []

    def office(key, name, level, institution, rank, note, src, anchor, locator=None):
        records.append({"id": f"ming_office_{key}", "name": name, "level": level,
                        "institution": institution, "rank": rank,
                        "period": "明中期制度参考（1500工作基准；全书沿革须逐年过滤）",
                        "note": note, "source_ids": [src],
                        "verification_status": "职名与概括职掌已核；1500逐地编额未全核",
                        "fact_kind": "原典职官条目概括，非现代行政机关类比",
                        "evidence": [evidence(src, locator or name + "条", anchor)]})

    office("emperor", "皇帝", "国家", "皇权", None, "朝廷最高决策角色；不是品官。玩家行动力为游戏机制。", "mingshi_015", "九月壬寅，即皇帝位")
    office("grand_secretary", "内阁大学士", "中央", "内阁", "本衔正五品；另有尚书及师保等兼衔", "参与机务、票拟与制诰。1500使用谨身殿、华盖殿旧名；中极、建极为嘉靖以后名称。", "mingshi_072", "文華殿大學士，武英殿大學士，文淵閣大學士，東閣大學士")
    departments = [
      ("personnel", "吏部", "吏部", "掌官员铨选、考核与封赠相关事务。"),
      ("revenue", "户部", "戶部", "掌户口、田土与钱粮赋役相关事务。"),
      ("rites", "礼部", "禮部", "掌礼仪、祭祀、学校科举与宾客相关事务。"),
      ("war", "兵部", "兵部", "掌武选、军务、车驾与武库相关事务；不等同直接统率所有军队。"),
      ("justice", "刑部", "刑部", "掌刑名、法律与审理相关事务，与都察院、大理寺互相衔接。"),
      ("works", "工部", "工部", "掌营造、水利、屯田与器用相关事务。"),
    ]
    for key, simple, trad, note in departments:
        office(key + "_minister", simple + "尚书", "中央", simple, "正二品", note,
               "mingshi_072", trad + "。尚書一人")
        office(key + "_vice_minister", simple + "左右侍郎", "中央", simple, "正三品",
               "辅佐尚书；左右职位须在具体任命时区分。" + note, "mingshi_072", trad + "。尚書一人")
    office("censor_left", "左都御史", "中央", "都察院", "正二品", "纠劾百司、参与考察与重大刑狱；1500正月闵珪在任。", "mingshi_073", "都察院。左、右都御史")
    office("censor_right", "右都御史", "中央／奉敕地方", "都察院", "正二品", "可掌院或奉敕出任地方任务，必须另记实际差遣。", "mingshi_073", "都察院。左、右都御史")
    office("deputy_censor", "左右副都御史", "中央／奉敕地方", "都察院", "正三品", "作为都察院官衔及巡抚等差遣所加官衔；差遣与官衔分开保存。", "mingshi_073", "左、右副都御史，正三品")
    office("assistant_censor", "左右佥都御史", "中央／奉敕地方", "都察院", "正四品", "官衔不直接等于固定省级行政首长。", "mingshi_073", "左、右僉都御史，正四品")
    office("inspecting_censor", "监察御史", "中央／巡按地方", "都察院十三道", "正七品", "监察纠举；巡按是差遣。暂不采用卷内万历后增员数字。", "mingshi_073", "十三道監察御史，主察糾內外百司之官邪")
    office("grand_coordinator", "巡抚（差遣）", "跨府／省区", "奉敕差遣", "随兼衔", "辖区与布政司边界不必重合；职权依敕书及兼衔。不得把清代统一督抚编制套入1500。", "mingshi_073", "其在外加都御史或副、僉都御史銜者")
    office("transmission_commissioner", "通政使", "中央", "通政使司", "正三品", "接收章奏、封驳与出纳帝命。", "mingshi_073", "通政使司。通政使一人")
    office("judicial_review_chief", "大理寺卿", "中央", "大理寺", "正三品", "审核刑狱并平反；机构编额及审理方式有时期变化。", "mingshi_073", "大理寺。卿一人，正三品")
    office("hanlin_academician", "翰林院学士", "中央", "翰林院", "正五品", "典制诰、史册与文翰等事务；不能将全部翰林官都归为学士一职。", "mingshi_073", "翰林院。學士一人")
    office("imperial_college_chief", "国子监祭酒", "中央", "国子监", "从四品", "国子监教育管理职官，为未来教育人才模块留资料。", "mingshi_073", "國子監。祭酒一人")
    office("sacrifices_chief", "太常寺卿", "中央", "太常寺", "正三品", "掌祭祀礼乐，听于礼部；嘉靖后祠署列表不直接移植。", "mingshi_074", "太常寺。卿一人，正三品")
    office("imperial_physician_chief", "太医院院使", "宫廷／中央", "太医院", "正五品", "医疗官署职官，作为未来健康与私生活模块的史料接口。", "mingshi_074", "太醫院。院使一人，正五品")
    office("sili_seal_eunuch", "司礼监掌印太监", "宫廷", "司礼监", None, "章奏、御前勘合等宫廷事务；本条只是制度参考，1500具体人名及分工待核。", "mingshi_074", "司禮監，提督太監一員")
    office("provincial_administration", "左右布政使", "省级", "承宣布政使司", "从二品", "掌省政、赋役等。两京直隶不设同样布政使司，不能一省一总督统一套用。", "mingshi_075", "承宣佈政使司。左、右布政使各一人")
    office("provincial_surveillance", "按察使", "省级", "提刑按察使司", "正三品", "掌一省刑名按劾，与布政、都司分立。", "mingshi_075", "提刑按察使司。按察使一人")
    office("provincial_participation", "左右参政", "省级／分道", "承宣布政使司", "从三品", "辅佐省政、分守及专项事务，具体派管因省而异。", "mingshi_075", "左、右參政，從三品")
    office("provincial_consultation", "左右参议", "省级／分道", "承宣布政使司", "从四品", "省级参佐，各地添设与派管不同。", "mingshi_075", "左、右參議，無定員。從四品")
    office("prefect", "知府", "府", "府", "正四品", "统理一府、考察属吏并总领所属政务；重大事务另有上报流程。", "mingshi_075", "府。知府一人，正四品")
    office("prefect_deputy", "府同知", "府", "府", "正五品", "分掌清军、管粮、治农、水利等，具体职责因府而异。", "mingshi_075", "同知，正五品；通判無定員")
    office("prefect_assistant", "府通判", "府", "府", "正六品", "府级佐贰，职责与设额非全国一致。", "mingshi_075", "通判無定員，正六品")
    office("prefect_judge", "府推官", "府", "府", "正七品", "理刑名、赞计典。", "mingshi_075", "推官理刑名，贊計典")
    office("department_magistrate", "知州", "州", "州", "从五品", "存在直隶州与属州；州不等同现代省，不能与布政司混为同层。", "mingshi_075", "州。知州一人，從五品")
    office("county_magistrate", "知县", "县", "县", "正七品", "统理县政；赋役、灾伤蠲免、审狱等留待后续权限规则。", "mingshi_075", "縣。知縣一人，正七品")
    office("county_deputy", "县丞", "县", "县", "正八品", "县级佐贰，分掌粮马巡捕等，部分小县裁省。", "mingshi_075", "縣丞一人，正八品")
    office("county_registrar", "县主簿", "县", "县", "正九品", "县级佐贰，与县丞的实际分工依县而异。", "mingshi_075", "主簿一人，正九品")
    office("county_clerk", "典史", "县", "县", "未入流", "典文移出纳；县丞或主簿缺设时可分领其职。", "mingshi_075", "典史典文移出納")
    office("nanjing_justice_minister", "南京刑部尚书", "南京中央官署", "南京刑部", "尚书品秩", "与北京刑部尚书分别保存；1500正月戴珊所任。", "mingshi_075", "刑部。尚書一人，右侍郎一人")
    office("six_sections", "六科给事中", "中央", "六科", "给事中从七品；都给事中正七品", "规谏、封驳与稽察六部；这是玩家劝谏机制的历史背景，诏书CD为游戏设计。", "mingshi_074", "吏、戶、禮、兵、刑、工六科。各都給事中一人")
    office("clan_court", "宗人府宗人令", "宗室／中央", "宗人府", "正一品", "掌皇族属籍；具体实任、兼领与后世省革待按年份细核。", "mingshi_072", "宗人府。宗人令一人")
    office("regional_military_commander", "都指挥使", "都司军政区", "都指挥使司", "正二品", "掌一方军政，率卫所，隶五军都督府并听于兵部；辖区不等于民政省界。", "mingshi_076", "都指揮使司。都指揮使一人")
    office("military_commission_vice", "都指挥同知", "都司军政区", "都指挥使司", "从二品", "可掌印、练兵、屯田或带俸，实际职掌另记。", "mingshi_076", "都指揮同知二人，從二品")
    office("military_commission_assistant", "都指挥佥事", "都司军政区", "都指挥使司", "正三品", "都司官衔；不能仅由官衔推定实领军队人数。", "mingshi_076", "都指揮僉事四人")
    office("battalion_commander", "正千户", "卫所", "千户所", "正五品", "卫所军官；额定与实有兵力分开，当前不初始化军额数值。", "mingshi_076", "所，千戶所，正千戶一人")
    office("company_commander", "百户", "卫所", "百户所", "正六品", "基层卫所官衔；史书额定兵额不作为1500实有兵数。", "mingshi_076", "共百戶十人，正六品")
    office("native_pacification", "宣慰使", "土司机构", "宣慰使司", "从三品", "土司职官参考，具体辖区、承袭和朝廷控制强弱需按地方资料核对。", "mingshi_076", "土官，宣慰使司，宣慰使一人")
    office("native_supervision", "宣抚使", "土司机构", "宣抚司", "从四品", "与宣慰司区分，不能自动视作普通府县。", "mingshi_076", "宣撫司，宣撫使一人")
    office("military_commissions", "五军都督府都督", "中央军事", "五军都督府", "左右都督正一品", "五府分领都司卫所并与兵部相衔接；不可简化为兵部下的单一将军树。", "mingshi_076", "都督府掌軍旅之事")
    office("guard_commander", "卫指挥使", "卫所", "卫指挥使司", "正三品", "可为世官或流官；是否掌印管事实任需单独保存。", "mingshi_076", "京衛指揮使司，指揮使一人，正三品")
    office("jinyi_guard", "锦衣卫（机构）", "皇帝亲军", "锦衣卫", None, "侍卫、缉捕及刑狱；为未来情报机构数据入口。1500具体领卫人、员额尚未核定。", "mingshi_076", "錦衣衛，掌侍衛、緝捕、刑獄之事")
    office("regional_commander", "总兵官（差遣）", "镇／军区", "镇守军务", "随本官衔；总兵差遣无独立品级", "与都督等本官衔区分。卷内晚明各镇名额不可整体投射到1500。", "mingshi_076", "總兵官、副總兵、參將、遊擊將軍、守備、把總，無品級")
    write("offices.json", records, "中央六部、内阁、监察、司法、宫廷及省府州县基本职官目录；并非1500全国实有编制表。")


def build_laws():
    records = []
    base = [
      ("appointments", "大臣专擅选官", "daminglv_02", "大臣專擅選官", "除授官员归朝廷选用，限制大臣擅自任命。具体授权例外须另查敕令。", "appointment"),
      ("imperial_orders", "制书有违", "daminglv_03", "制書有違", "区分奉制执行中的违旨、失错和迟延，供未来命令执行系统参考。", "orders"),
      ("reporting", "事应奏不奏", "daminglv_03", "事應奏不奏", "规定应奏、应申事项的上报责任及擅自施行责任，不能推成所有地方事务一律请旨。", "reporting"),
      ("paperwork", "官文书稽程", "daminglv_03", "官文書稽程", "对官文书迟延、含糊推调等规定责任，供未来传递与官僚效率模块参考。", "administration"),
      ("registration", "人户以籍为定", "daminglv_04", "人戶以籍為定", "以既定户籍约束户类及差役归属；户籍人口不直接等于实际人口。", "population"),
      ("disaster_survey", "检踏灾伤田粮", "daminglv_05", "檢踏災傷田糧", "灾伤田粮需申报与检验，对虚报、失实勘报等有规定。", "relief"),
      ("tax_measure", "多收税粮斛面", "daminglv_07", "多收稅糧斛面", "约束收粮量器与额外多收；实际折耗与附例属于另需按年代校核的层次。", "taxation"),
      ("bribery", "官吏受财", "daminglv_23", "官吏受財", "区分枉法、不枉法等受财情形；不据此直接生成抽象腐败度或刑罚数值。", "corruption"),
      ("levees", "失时不修堤防", "daminglv_30", "失時不修隄防", "规定堤防维护责任，并区分非人力所能控制的暴水连雨情形。", "infrastructure"),
      ("roads", "修理桥梁道路", "daminglv_30", "修理橋梁道路", "府州县佐贰在农隙检查修理桥梁道路并维持交通。", "infrastructure"),
    ]
    for key, name, source, anchor, summary, domain in base:
        records.append({"id": "ming_law_" + key, "name": name, "category": "律文主题",
                        "domain": domain, "summary": summary,
                        "period": "洪武定律传统；1500年作为律文主题参考，所用载体含后世集解附例",
                        "source_ids": [source, "mingshi_093"],
                        "verification_status": "条名与正文已核；1500字句版本及附例适用性待复校",
                        "fact_kind": "律文主题概括；非完整法制复原",
                        "effective_at_baseline": "reference_only_pending_edition_collation",
                        "simulation_effects_enabled": False,
                        "evidence": [evidence(source, "律文条目：" + anchor + "（不取后附条例为1500事实）", anchor, 210)],
                        "implementation_note": "只在史料页陈列。诏书上限、政务CD、忠心声誉惩罚属于用户设计，不来自本律。"})
    for key, name, anchor, when, summary in [
      ("grain_reserves_1490", "命预备仓积粟", "命天下預備倉積粟", "弘治三年（1490）三月", "本纪记命天下预备仓积粟，以里数多寡为差；仅记录已颁命令，不推定1500各地实际库存与执行效果。"),
      ("assessment_1495", "考察官员务得实迹", "諭吏部、都察院，人材進退", "弘治八年（1495）四月", "要求吏部、都察院考察人才进退依据实迹、避免偏听枉人。")]:
        records.append({"id": "ming_edict_" + key, "name": name, "category": "有纪年的诏令记录",
                        "summary": summary, "period": when, "source_ids": ["mingshi_015"],
                        "verification_status": "本纪日期与命令内容已核",
                        "fact_kind": "史料直接记载", "effective_at_baseline": "past_edict_reference",
                        "simulation_effects_enabled": False,
                        "evidence": [evidence("mingshi_015", when, anchor)]})
    records.append({"id": "ming_law_wenxing_1500", "name": "弘治问刑条例重定", "category": "开局之后的制度事件参考",
                    "summary": "弘治十三年二月重定问刑条例。《明史·刑法》记增历年可行者297条；不能在正月开局就声明其全部已生效，也不能把后世附例整本替代本次条例。",
                    "period": "弘治十三年（1500）二月，晚于本包正月基准", "source_ids": ["mingshi_015", "mingshi_093", "mingtongjian_043"],
                    "verification_status": "制定时间及总数互核；297条独立版本尚未完整校录",
                    "fact_kind": "史料直接记载及开局先后判断", "effective_at_baseline": False,
                    "simulation_effects_enabled": False,
                    "evidence": [evidence("mingshi_015", "弘治十三年二月", "庚寅，定問刑條例"),
                                 evidence("mingshi_093", "弘治十三年问刑条例", "增歷年問刑條例經久可行者二百九十七條"),
                                 evidence("mingtongjian_043", "弘治十三年二月", "庚寅，诏更定刑部条律")]})
    write("laws.json", records, "10条基本律文主题、2项开局前诏令与1项开局后二月制度事件；未把任何法令转换成数值模拟。")


if __name__ == "__main__":
    build_people()
    build_offices()
    build_laws()
    for filename in ("people.json", "offices.json", "laws.json"):
        payload = json.loads((DEST / filename).read_text(encoding="utf-8"))
        print(filename, len(payload["records"]))
