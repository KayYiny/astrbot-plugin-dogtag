"""
Dog Tag 插件 for AstrBot
注册管理狗牌身份，管理名字、生日和装备
"""

import re
import json
from datetime import datetime, date, timedelta
from pathlib import Path

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
import astrbot.api.message_components as Comp


@register("dogtag", "KayYiny", "一个通用的 Dog Tag 插件，支持注册、管理个人信息和装备", "1.3.3", "https://github.com/KayYiny/astrbot-plugin-dogtag")
class Main(Star):
    def __init__(self, context: Context, config: AstrBotConfig) -> None:
        super().__init__(context)
        self.config = config
        self.data_dir = Path("data") / "plugin_data" / "astrbot-plugin-dogtag"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Dog Tag 插件已加载")

    def _get_config_value(self, key: str, default):
        return self.config.get(key, default)

    def _get_user_file(self, sid: str) -> Path:
        safe_sid = re.sub(r'[^a-zA-Z0-9_]', '_', sid)
        return self.data_dir / f"{safe_sid}.json"

    def _load_user_data(self, sid: str):
        user_file = self._get_user_file(sid)
        if user_file.exists():
            with open(user_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

    def _save_user_data(self, sid: str, data: dict) -> None:
        user_file = self._get_user_file(sid)
        temp_file = user_file.with_suffix(".tmp")
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        temp_file.replace(user_file)

    def _find_user_by_name(self, name: str):
        name = name.strip()
        for f in self.data_dir.glob("*.json"):
            try:
                d = json.load(open(f, 'r', encoding='utf-8'))
                if d.get('name') == name:
                    return d
            except Exception:
                continue
        return None

    def _require_registered(self, event: AstrMessageEvent):
        sid = event.get_sender_id()
        user_data = self._load_user_data(sid)
        if not user_data:
            if self._get_config_value("show_register_tips", True):
                return None, "❌ 你还没有注册！请先使用 /注册 <名字> 进行注册。"
            return None, "❌ 你还没有注册！"
        nick = event.get_sender_name()
        if nick and user_data.get('name') != nick:
            user_data['name'] = nick
            self._save_user_data(sid, user_data)
        return sid, user_data

    def _calculate_age(self, birthday_str: str) -> str:
        try:
            bd = datetime.strptime(birthday_str, "%Y.%m.%d").date()
            today = date.today()
            y = today.year - bd.year
            if (today.month, today.day) < (bd.month, bd.day):
                y -= 1
            return f"{y}岁"
        except Exception:
            return "未设置"

    def _is_birthday_today(self, birthday_str: str) -> bool:
        try:
            bd = datetime.strptime(birthday_str, "%Y.%m.%d").date()
            today = date.today()
            return (bd.month, bd.day) == (today.month, today.day)
        except Exception:
            return False

    def _format_duration(self, seconds: int) -> str:
        if seconds < 0: seconds = 0
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        d, h = divmod(h, 24)
        if d >= 365:
            y = d // 365; r = d % 365; mo = r // 30
            return f"{y}年{mo}月" if r % 30 else f"{y}年"
        if d >= 30:
            mo = d // 30; r = d % 30
            return f"{mo}月{r}天" if r else f"{mo}月"
        if d >= 7:
            w = d // 7; r = d % 7
            return f"{w}周{r}天" if r else f"{w}周"
        parts = []
        if d: parts.append(f"{d}天")
        if h: parts.append(f"{h}小时")
        if m: parts.append(f"{m}分")
        if s or not parts: parts.append(f"{s}秒")
        return "".join(parts)

    def _parse_duration(self, text: str):
        units = {'天': 86400, '日': 86400, '小时': 3600, '时': 3600, '分': 60, '分钟': 60, '秒': 1}
        total = 0
        for match in re.finditer(r'(\d+)\s*(天|日|小时|时|分|分钟|秒)', text):
            total += int(match.group(1)) * units.get(match.group(2), 0)
        return total if total > 0 else None

    def _handle_register(self, event: AstrMessageEvent, input_name: str) -> str:
        sid = event.get_sender_id()
        if self._load_user_data(sid):
            return "❌ 你已经注册过了！可以使用 /改名 来修改名字。"
        if not input_name or not input_name.strip():
            return "❌ 请提供一个名字！使用方法：/注册 <名字>"
        input_name = input_name.strip()
        if len(input_name) > self._get_config_value("max_name_length", 20):
            return f"❌ 名字太长了！最多 {self._get_config_value('max_name_length', 20)} 个字符。"
        prefix = self._get_config_value("custom_name_prefix", "")
        display_name = prefix + input_name if prefix else input_name
        nick = event.get_sender_name() or ""
        user_data = {
            "id": sid, "name": nick, "display_name": display_name,
            "birthday": None, "register_date": datetime.now().strftime("%Y-%m-%d"),
            "equipment": {}, "equipment_history": {}, "pending_gift": None
        }
        self._save_user_data(sid, user_data)
        return f"✅ 注册成功！欢迎你，{display_name}！🐶"

    def _handle_rename(self, event: AstrMessageEvent, new_name: str) -> str:
        r = self._require_registered(event)
        if r[0] is None: return r[1]
        sid, user_data = r
        if not new_name or not new_name.strip():
            return "❌ 请提供一个新名字！使用方法：/改名 <新名字>"
        new_name = new_name.strip()
        if len(new_name) > self._get_config_value("max_name_length", 20):
            return f"❌ 名字太长了！最多 {self._get_config_value('max_name_length', 20)} 个字符。"
        prefix = self._get_config_value("custom_name_prefix", "")
        display_name = prefix + new_name if prefix else new_name
        old = user_data.get('display_name', '未知')
        user_data['display_name'] = display_name
        self._save_user_data(sid, user_data)
        return f"✅ 改名成功！{old} → {display_name}"

    def _handle_birthday(self, event: AstrMessageEvent, birthday: str) -> str:
        r = self._require_registered(event)
        if r[0] is None: return r[1]
        sid, user_data = r
        try:
            datetime.strptime(birthday, "%Y.%m.%d")
        except ValueError:
            return "❌ 日期格式错误！请使用格式：yyyy.mm.dd（例如：2020.05.15）"
        user_data['birthday'] = birthday
        self._save_user_data(sid, user_data)
        return f"✅ 生日设置成功！你的诞生日是 {birthday}，现在的年龄是 {self._calculate_age(birthday)}！🎂"

    def _format_equipment_list(self, equipment: dict) -> str:
        if not equipment:
            return "🎒 当前没有佩戴任何装备。\n💡 使用 /装备 <名字> 来佩戴。"
        lines = [f"🎒 当前装备（{len(equipment)}个）："]
        for name, info in equipment.items():
            try:
                dur = int((datetime.now() - datetime.fromisoformat(info['start_time'])).total_seconds())
                ds = self._format_duration(dur)
            except Exception:
                ds = "计时中"
            from_txt = f" 来自{info['from']}" if info.get('from') else ""
            lines.append(f"  {name}（{ds}）{from_txt}")
        return "\n".join(lines)

    def _handle_equip(self, event: AstrMessageEvent, equip_name: str) -> str:
        r = self._require_registered(event)
        if r[0] is None: return r[1]
        sid, user_data = r
        if not equip_name or not equip_name.strip():
            return "❌ 请提供装备名字！使用方法：/装备 <装备名字>"
        equip_name = equip_name.strip()
        if len(equip_name) > self._get_config_value("max_equip_name_length", 6):
            return f"❌ 装备名字太长了！最多 {self._get_config_value('max_equip_name_length', 6)} 个字符。"
        if equip_name in user_data.get('equipment', {}):
            return f"❌ 已经带上了「{equip_name}」，没有位置！"
        max_e = self._get_config_value("max_equipment", 0)
        if max_e > 0 and len(user_data.get('equipment', {})) >= max_e:
            return "❌ 没有位置了！"
        user_data['equipment'][equip_name] = {"start_time": datetime.now().isoformat()}
        self._save_user_data(sid, user_data)
        return f"✅ 已装备「{equip_name}」！⏱️"

    def _handle_unequip(self, event: AstrMessageEvent, equip_name: str) -> str:
        r = self._require_registered(event)
        if r[0] is None: return r[1]
        sid, user_data = r
        if not equip_name or not equip_name.strip():
            return "❌ 请提供装备名字！使用方法：/取下 <装备名字>"
        equip_name = equip_name.strip()
        if equip_name not in user_data.get('equipment', {}):
            return f"❌ 你得先带上「{equip_name}」哟！"
        info = user_data['equipment'].pop(equip_name)
        dur = int((datetime.now() - datetime.fromisoformat(info['start_time'])).total_seconds())
        dur_str = self._format_duration(dur)
        old_max = user_data.setdefault('equipment_history', {}).get(equip_name, {}).get('max_duration', 0)
        msg = f"✅ 已取下「{equip_name}」！佩戴时间：{dur_str}"
        if dur > old_max:
            user_data['equipment_history'][equip_name] = {
                "max_duration": dur, "max_duration_str": dur_str,
                "date": date.today().strftime("%Y-%m-%d")
            }
            msg += f"\n🏆 新纪录！刷新了历史最长佩戴时间！"
        else:
            msg += f"\n历史最长记录：{self._format_duration(old_max)}，再加油哟"
        self._save_user_data(sid, user_data)
        return msg

    def _handle_backdate(self, event: AstrMessageEvent, equip_name: str, duration_text: str) -> str:
        r = self._require_registered(event)
        if r[0] is None: return r[1]
        sid, user_data = r
        if not equip_name or not equip_name.strip():
            return "❌ 请提供装备名字！使用方法：/装备补时 <装备名> <时长>"
        equip_name = equip_name.strip()
        if len(equip_name) > self._get_config_value("max_equip_name_length", 6):
            return f"❌ 装备名字太长了！最多 {self._get_config_value('max_equip_name_length', 6)} 个字符。"
        seconds = self._parse_duration(duration_text)
        if seconds is None:
            return "❌ 时长格式无效！例如：/装备补时 手表 5天"
        start = (datetime.now() - timedelta(seconds=seconds)).isoformat()
        is_new = equip_name not in user_data.get('equipment', {})
        user_data['equipment'][equip_name] = {"start_time": start}
        self._save_user_data(sid, user_data)
        ds = self._format_duration(seconds)
        if is_new:
            return f"✅ 已装备「{equip_name}」，补时 {ds}！⏱️"
        return f"✅ 已将「{equip_name}」的时长调整为 {ds}！⏱️"

    def _handle_gift(self, event: AstrMessageEvent, target_sid: str, equip_name: str) -> str:
        sid = event.get_sender_id()
        sender = self._load_user_data(sid)
        if not sender:
            return "❌ 你还没有注册狗牌哦"
        if len(equip_name) > self._get_config_value("max_equip_name_length", 6):
            return f"❌ 装备名字太长了！最多 {self._get_config_value('max_equip_name_length', 6)} 个字符。"
        target = self._load_user_data(target_sid)
        if not target:
            return "❌ 对方还没有注册狗牌哦"
        if target.get('pending_gift'):
            return "❌ 对方已有待确认的赠送请求，请等 Ta 处理完再送"
        sender_name = sender.get('display_name') or sender.get('name', sid)
        target['pending_gift'] = {
            "from_sid": sid, "from_name": sender_name,
            "equip_name": equip_name, "timestamp": datetime.now().isoformat()
        }
        self._save_user_data(target_sid, target)
        return f"✅ 已送出「{equip_name}」给 {target.get('display_name', '对方')}，等待对方确认中..."

    def _handle_accept(self, event: AstrMessageEvent) -> str:
        r = self._require_registered(event)
        if r[0] is None: return r[1]
        sid, user_data = r
        gift = user_data.get('pending_gift')
        if not gift:
            return "❌ 你目前没有待确认的赠送请求"
        en, fn = gift['equip_name'], gift['from_name']
        if en in user_data.get('equipment', {}):
            del user_data['pending_gift']
            self._save_user_data(sid, user_data)
            return f"❌ 你已经有了「{en}」，无法接受重复装备"
        max_e = self._get_config_value("max_equipment", 0)
        if max_e > 0 and len(user_data.get('equipment', {})) >= max_e:
            del user_data['pending_gift']
            self._save_user_data(sid, user_data)
            return "❌ 你的装备位已满，无法接受"
        user_data['equipment'][en] = {"start_time": datetime.now().isoformat(), "from": fn}
        del user_data['pending_gift']
        self._save_user_data(sid, user_data)
        return f"✅ 你接受了 {fn} 的「{en}」！"

    def _handle_reject(self, event: AstrMessageEvent) -> str:
        r = self._require_registered(event)
        if r[0] is None: return r[1]
        sid, user_data = r
        gift = user_data.get('pending_gift')
        if not gift:
            return "❌ 你目前没有待确认的赠送请求"
        en, fn = gift['equip_name'], gift['from_name']
        del user_data['pending_gift']
        self._save_user_data(sid, user_data)
        return f"❌ 你拒绝了 {fn} 的「{en}」"

    def _handle_info(self, event: AstrMessageEvent) -> str:
        r = self._require_registered(event)
        if r[0] is None: return r[1]
        _, user_data = r
        name = user_data.get('display_name', '未知')
        if user_data.get('birthday'):
            age = self._calculate_age(user_data['birthday'])
            bd = f"\n🎂 年龄：{age}"
            if self._get_config_value("birthday_reminder_enabled", True) and self._is_birthday_today(user_data['birthday']):
                bd += "\n🎉 今天是你的生日！生日快乐！"
        else:
            bd = "\n🎂 年龄：未设置"
        equip = []
        for en, ei in user_data.get('equipment', {}).items():
            try:
                dur = int((datetime.now() - datetime.fromisoformat(ei['start_time'])).total_seconds())
                ds = self._format_duration(dur)
            except Exception:
                ds = "计时中"
            from_txt = f" 来自{ei['from']}" if ei.get('from') else ""
            equip.append(f"        {en}（{ds}）{from_txt}")
        eq_txt = "\n" + "\n".join(equip) if equip else "（无）"
        return f"""🐶 狗牌信息 🐶
━━━━━━━━━━━━━━━
👤 名字：{name}{bd}
🎒 装备：{eq_txt}
━━━━━━━━━━━━━━━"""

    @filter.command("注册")
    async def register_user(self, event: AstrMessageEvent):
        parts = event.message_str.split(maxsplit=1)
        if len(parts) < 2:
            yield event.plain_result("❌ 请提供名字！使用方法：/注册 <名字>")
            return
        yield event.plain_result(self._handle_register(event, parts[1].strip()))

    @filter.command("改名")
    async def rename(self, event: AstrMessageEvent):
        parts = event.message_str.split(maxsplit=1)
        if len(parts) < 2:
            yield event.plain_result("❌ 请提供新名字！使用方法：/改名 <新名字>")
            return
        yield event.plain_result(self._handle_rename(event, parts[1].strip()))

    @filter.command("生日")
    async def set_birthday(self, event: AstrMessageEvent):
        parts = event.message_str.split(maxsplit=1)
        if len(parts) < 2:
            yield event.plain_result("❌ 请提供生日！使用方法：/生日 yyyy.mm.dd")
            return
        yield event.plain_result(self._handle_birthday(event, parts[1].strip()))

    @filter.command("装备")
    async def equip(self, event: AstrMessageEvent):
        parts = event.message_str.split(maxsplit=1)
        if len(parts) < 2:
            r = self._require_registered(event)
            if r[0] is None:
                yield event.plain_result(r[1])
                return
            yield event.plain_result(self._format_equipment_list(r[1].get('equipment', {})))
            return
        yield event.plain_result(self._handle_equip(event, parts[1].strip()))

    @filter.command("取下")
    async def unequip(self, event: AstrMessageEvent):
        parts = event.message_str.split(maxsplit=1)
        if len(parts) < 2:
            yield event.plain_result("❌ 请提供装备名字！使用方法：/取下 <装备名字>")
            return
        yield event.plain_result(self._handle_unequip(event, parts[1].strip()))

    @filter.command("装备补时")
    async def backdate(self, event: AstrMessageEvent):
        parts = event.message_str.split(maxsplit=2)
        if len(parts) < 3:
            yield event.plain_result("❌ 使用方法：/装备补时 <装备名> <时长>（例如：/装备补时 手表 5天）")
            return
        yield event.plain_result(self._handle_backdate(event, parts[1].strip(), parts[2].strip()))

    @filter.command("送")
    async def send_gift(self, event: AstrMessageEvent):
        parts = event.message_str.split(maxsplit=1)
        if len(parts) < 2:
            yield event.plain_result("❌ 使用方法：/送 @对方 <装备名>（例如：/送 @小B 手表）")
            return
        target_sid = None
        for comp in event.message_obj.message:
            if isinstance(comp, Comp.At):
                target_sid = str(comp.qq)
                break
        if not target_sid:
            yield event.plain_result("❌ 请 @ 要赠送的群友")
            return
        m = re.search(r'@\S+\s+(.+)', parts[1])
        if not m:
            yield event.plain_result("❌ 请提供装备名字！使用方法：/送 @对方 <装备名>")
            return
        equip_name = m.group(1).strip()
        result = self._handle_gift(event, target_sid, equip_name)
        if result.startswith("❌"):
            yield event.plain_result(result)
            return
        yield event.chain_result([
            Comp.Plain(result + "\n"),
            Comp.At(qq=target_sid),
            Comp.Plain(f" 收到了一份礼物！「{equip_name}」\n使用 /同意 接受，或 /拒绝 拒绝"),
        ])

    @filter.command("同意")
    async def accept_gift(self, event: AstrMessageEvent):
        yield event.plain_result(self._handle_accept(event))

    @filter.command("拒绝")
    async def reject_gift(self, event: AstrMessageEvent):
        yield event.plain_result(self._handle_reject(event))

    @filter.command("狗牌")
    async def show_info(self, event: AstrMessageEvent):
        yield event.plain_result(self._handle_info(event))

    @filter.command("看")
    async def view_other(self, event: AstrMessageEvent):
        parts = event.message_str.split(maxsplit=1)
        if len(parts) < 2:
            yield event.plain_result("❌ 请指定要查看的群友，例如：/看 @小B")
            return
        target = None
        for comp in event.message_obj.message:
            if isinstance(comp, Comp.At):
                target = self._load_user_data(str(comp.qq))
                break
        if not target:
            m = re.search(r'@(.+)', parts[1])
            if m:
                target = self._find_user_by_name(m.group(1).strip())
        if not target:
            yield event.plain_result("❌ 没有找到该群友的狗牌哦")
            return
        dn = target.get('display_name') or target.get('name', '未知')
        eq = target.get('equipment', {})
        if eq:
            ep = []
            for en, ei in eq.items():
                try:
                    dur = int((datetime.now() - datetime.fromisoformat(ei['start_time'])).total_seconds())
                    ds = self._format_duration(dur)
                except Exception:
                    ds = "计时中"
                from_txt = f" 来自{ei['from']}" if ei.get('from') else ""
                ep.append(f"{en}（{ds}）{from_txt}")
            eq_txt = " ".join(ep)
        else:
            eq_txt = "（无）"
        yield event.plain_result(f"🐶 {dn} 🎒 {eq_txt}")

    @filter.command("狗牌帮助")
    async def help(self, event: AstrMessageEvent):
        sid = event.get_sender_id()
        ud = self._load_user_data(sid)
        if not ud:
            yield event.plain_result("""🐶 欢迎来到 Dog Tag！

📋 三步开始
  1. 注册：/注册 <名字>
  2. 生日：/生日 2020.05.15
  3. 查看：/狗牌

🎒 装备
  /装备 <名字>  佩戴
  /装备          查看当前
  /取下 <名字>  取下
  /装备补时 <名> <时长>  回溯时长

🎁 赠送
  /送 @对方 <装备名>  赠送
  /同意          接受
  /拒绝          拒绝

👀 互动
  /看 @群友  查看对方狗牌""")
        else:
            yield event.plain_result(f"""🐶 {ud.get('display_name', '未知')} 的操作指南

📝 个人信息
  /改名 <新名字>  改名
  /生日 yyyy.mm.dd  设置生日
  /狗牌          查看狗牌

🎒 装备
  /装备 <名字>  佩戴
  /装备          查看当前
  /取下 <名字>  取下
  /装备补时 <名> <时长>  回溯时长

🎁 赠送
  /送 @对方 <装备名>  赠送
  /同意          接受
  /拒绝          拒绝

👀 互动
  /看 @群友  查看对方狗牌""")

    async def terminate(self):
        logger.info("Dog Tag 插件已卸载")
