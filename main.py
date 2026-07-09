"""
Dog Tag 插件 for AstrBot
注册管理狗牌身份，管理名字、生日和装备
"""

import re
import json
from datetime import datetime, date
from pathlib import Path

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig


@register("dogtag", "KayYiny", "Dog Tag 插件，支持注册、管理个人信息和装备", "1.1.0", "https://github.com/KayYiny/astrbot-plugin-dogtag")
class Main(Star):
    def __init__(self, context: Context, config: AstrBotConfig) -> None:
        super().__init__(context)
        self.config = config
        self.data_dir = Path("data") / "plugin_data" / "astrbot-plugin-dogtag"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Dog Tag 插件已加载")

    def _get_config_value(self, key: str, default):
        return self.config.get(key, default)

    def _is_operation_allowed(self, event: AstrMessageEvent) -> bool:
        if self._get_config_value("allow_group_register", False):
            return True
        return event.is_private_chat()

    def _get_private_error_msg(self) -> str:
        return "❌ 此操作只能在私聊环境中使用！可以联系管理员在配置中开启群聊权限。"

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

    def _require_registered(self, event: AstrMessageEvent):
        if not self._is_operation_allowed(event):
            return None, self._get_private_error_msg()
        sid = event.get_sender_id()
        user_data = self._load_user_data(sid)
        if not user_data:
            if self._get_config_value("show_register_tips", True):
                return None, "❌ 你还没有注册！请先使用 /注册 <名字> 进行注册。"
            return None, "❌ 你还没有注册！"
        return sid, user_data

    def _calculate_age(self, birthday_str: str) -> str:
        try:
            birth_date = datetime.strptime(birthday_str, "%Y.%m.%d").date()
            today = date.today()
            age_years = today.year - birth_date.year
            if (today.month, today.day) < (birth_date.month, birth_date.day):
                age_years -= 1
            return f"{age_years}岁"
        except Exception:
            return "未设置"

    def _is_birthday_today(self, birthday_str: str) -> bool:
        try:
            birth_date = datetime.strptime(birthday_str, "%Y.%m.%d").date()
            today = date.today()
            return (birth_date.month, birth_date.day) == (today.month, today.day)
        except Exception:
            return False

    def _format_duration(self, seconds: int) -> str:
        if seconds < 0:
            seconds = 0
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        d, h = divmod(h, 24)
        if d >= 365:
            y = d // 365
            r = d % 365
            mo = r // 30
            return f"{y}年{mo}月" if r % 30 else f"{y}年"
        if d >= 30:
            mo = d // 30
            r = d % 30
            return f"{mo}月{r}天" if r else f"{mo}月"
        if d >= 7:
            w = d // 7
            r = d % 7
            return f"{w}周{r}天" if r else f"{w}周"
        parts = []
        if d: parts.append(f"{d}天")
        if h: parts.append(f"{h}小时")
        if m: parts.append(f"{m}分")
        if s or not parts: parts.append(f"{s}秒")
        return "".join(parts)

    def _handle_register(self, event: AstrMessageEvent, input_name: str) -> str:
        if not self._is_operation_allowed(event):
            return self._get_private_error_msg()
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
            "equipment": {}, "equipment_history": {}
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
                dur_str = self._format_duration(dur)
            except Exception:
                dur_str = "计时中"
            lines.append(f"  {name}（{dur_str}）")
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
            return "❌ 请提供装备名字！使用方法：/取下装备 <装备名字>"
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
            equip.append(f"        {en}（{ds}）")
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

    @filter.command("我的诞生日")
    async def set_birthday(self, event: AstrMessageEvent):
        parts = event.message_str.split(maxsplit=1)
        if len(parts) < 2:
            yield event.plain_result("❌ 请提供生日！使用方法：/我的诞生日 yyyy.mm.dd")
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

    @filter.command("取下装备")
    async def unequip(self, event: AstrMessageEvent):
        parts = event.message_str.split(maxsplit=1)
        if len(parts) < 2:
            yield event.plain_result("❌ 请提供装备名字！使用方法：/取下装备 <装备名字>")
            return
        yield event.plain_result(self._handle_unequip(event, parts[1].strip()))

    @filter.command("我的信息")
    async def show_info(self, event: AstrMessageEvent):
        yield event.plain_result(self._handle_info(event))

    @filter.command("帮助")
    async def help(self, event: AstrMessageEvent):
        sid = event.get_sender_id()
        ud = self._load_user_data(sid)
        if not ud:
            yield event.plain_result("""🐶 欢迎来到 Dog Tag！

📋 三步开始
  1. 注册：/注册 <名字>
  2. 生日：/我的诞生日 2020.05.15
  3. 查看：/我的信息

🎒 装备
  /装备 <名字>  佩戴
  /装备          查看当前
  /取下装备 <名字>  取下""")
        else:
            yield event.plain_result(f"""🐶 {ud.get('display_name', '未知')} 的操作指南

📝 个人信息
  /改名 <新名字>  改名
  /我的诞生日 yyyy.mm.dd  设置生日
  /我的信息      查看卡片

🎒 装备
  /装备 <名字>  佩戴
  /装备          查看当前
  /取下装备 <名字>  取下""")

    async def terminate(self):
        logger.info("Dog Tag 插件已卸载")
