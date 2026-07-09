"""
Dog Tag 插件 for AstrBot
注册管理狗牌身份，管理名字、生日
"""

import re
import json
from datetime import datetime, date
from pathlib import Path

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig


@register("dogtag", "KayYiny", "Dog Tag 插件，支持注册、管理个人信息", "1.0.0", "https://github.com/KayYiny/astrbot-plugin-dogtag")
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

    def _handle_register(self, event: AstrMessageEvent, input_name: str) -> str:
        if not self._is_operation_allowed(event):
            return self._get_private_error_msg()
        sid = event.get_sender_id()
        if self._load_user_data(sid):
            return "❌ 你已经注册过了！可以使用 /改名 来修改名字。"
        if not input_name or not input_name.strip():
            return "❌ 请提供一个名字！使用方法：/注册 <名字>"
        input_name = input_name.strip()
        max_length = self._get_config_value("max_name_length", 20)
        if len(input_name) > max_length:
            return f"❌ 名字太长了！最多 {max_length} 个字符。"
        prefix = self._get_config_value("custom_name_prefix", "")
        display_name = prefix + input_name if prefix else input_name
        nick = event.get_sender_name() or ""
        user_data = {
            "id": sid, "name": nick, "display_name": display_name,
            "birthday": None, "register_date": datetime.now().strftime("%Y-%m-%d")
        }
        self._save_user_data(sid, user_data)
        return f"✅ 注册成功！欢迎你，{display_name}！🐶"

    def _handle_rename(self, event: AstrMessageEvent, new_name: str) -> str:
        r = self._require_registered(event)
        if r[0] is None:
            return r[1]
        sid, user_data = r
        if not new_name or not new_name.strip():
            return "❌ 请提供一个新名字！使用方法：/改名 <新名字>"
        new_name = new_name.strip()
        max_length = self._get_config_value("max_name_length", 20)
        if len(new_name) > max_length:
            return f"❌ 名字太长了！最多 {max_length} 个字符。"
        prefix = self._get_config_value("custom_name_prefix", "")
        display_name = prefix + new_name if prefix else new_name
        old_display = user_data.get('display_name', '未知')
        user_data['display_name'] = display_name
        self._save_user_data(sid, user_data)
        return f"✅ 改名成功！{old_display} → {display_name}"

    def _handle_birthday(self, event: AstrMessageEvent, birthday: str) -> str:
        r = self._require_registered(event)
        if r[0] is None:
            return r[1]
        sid, user_data = r
        try:
            datetime.strptime(birthday, "%Y.%m.%d")
        except ValueError:
            return "❌ 日期格式错误！请使用格式：yyyy.mm.dd（例如：2020.05.15）"
        user_data['birthday'] = birthday
        self._save_user_data(sid, user_data)
        age = self._calculate_age(birthday)
        return f"✅ 生日设置成功！你的诞生日是 {birthday}，现在的年龄是 {age}！🎂"

    def _handle_info(self, event: AstrMessageEvent) -> str:
        r = self._require_registered(event)
        if r[0] is None:
            return r[1]
        _, user_data = r
        name = user_data.get('display_name', '未知')
        if user_data.get('birthday'):
            age = self._calculate_age(user_data['birthday'])
            birthday_text = f"\n🎂 年龄：{age}"
            if self._get_config_value("birthday_reminder_enabled", True) and self._is_birthday_today(user_data['birthday']):
                birthday_text += "\n🎉 今天是你的生日！生日快乐！"
        else:
            birthday_text = "\n🎂 年龄：未设置"
        return f"""🐶 狗牌信息 🐶
━━━━━━━━━━━━━━━
👤 名字：{name}{birthday_text}
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

    @filter.command("我的信息")
    async def show_info(self, event: AstrMessageEvent):
        yield event.plain_result(self._handle_info(event))

    @filter.command("帮助")
    async def help(self, event: AstrMessageEvent):
        sid = event.get_sender_id()
        user_data = self._load_user_data(sid)
        if not user_data:
            yield event.plain_result("""🐶 欢迎来到 Dog Tag！

📋 三步开始
  1. 注册：/注册 <名字>
  2. 生日：/我的诞生日 2020.05.15
  3. 查看：/我的信息""")
        else:
            yield event.plain_result(f"""🐶 {user_data.get('display_name', '未知')} 的操作指南

📝 个人信息
  /改名 <新名字>  改名
  /我的诞生日 yyyy.mm.dd  设置生日
  /我的信息      查看卡片""")

    async def terminate(self):
        logger.info("Dog Tag 插件已卸载")
