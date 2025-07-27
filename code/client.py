# 文件: client.py (已完全适配 Public/Private 分离结构)

import socketio
import requests
import threading
import time
import json
import sys
import os
from datetime import datetime

# --- 配置和全局变量 (已修改) ---
sio = socketio.Client()
_replacements = {
    '1o': '🀙', '2o': '🀚', '3o': '🀛', '4o': '🀜', '5o': '🀝', '6o': '🀞', '7o': '🀟', '8o': '🀠', '9o': '🀡',
    '1t': '🀐', '2t': '🀑', '3t': '🀒', '4t': '🀓', '5t': '🀔', '6t': '🀕', '7t': '🀖', '8t': '🀗', '9t': '🀘',
    '1w': '🀇', '2w': '🀈', '3w': '🀉', '4w': '🀊', '5w': '🀋', '6w': '🀌', '7w': '🀍', '8w': '🀎', '9w': '🀏',
    'e': '🀀', 's': '🀁', 'w': '🀂', 'n': '🀃', 'b': '🀆', 'f': '🀅', 'z': '🀄', 'joker': '🃏', 'back': '🀫',
    'spring': '🀦', 'summer': '🀧', 'autumn': '🀨', 'winter': '🀩',
    'plum': '🀢', 'orchid': '🀣', 'bamboo': '🀤', 'chrysanthemum': '🀥'
}
last_refresh_time = time.time()
current_user = {'name': '', 'server': '', 'connected': False, 'in_room': False, 'room_id': None, 'is_ready': False}
current_room = {'name': 'Unknown', 'id': None, 'owner': 'Unknown', 'game': None, 'members': {}, 'messages': [], 'rules': {}, 'status': '', 'logs': []}
room_list = []
should_exit = threading.Event()
displayed_actions = []

# 【核心修改】初始化 current_game_state 的新结构
current_game_state = {
    'public': {},
    'private': {}
}

# --- Public: ---
# "status": self.status,
# "playerindex": self.playerindex,
# "winner_id": self.winner_id,
# "wall_count": len(self.wall),
# "players": [
#     {
#         "id": p.id,
#         "name": p.name,
#         "hand_count": len(p.hands),
#         "locked": p.locked,
#         "discarded": p.discarded
#     } for p in self.players
# ],
# "report": ""

# --- Private: ---
# "hands": self.players[playerid].hands,
# "locked": self.players[playerid].locked,
# "new": self.players[playerid].new,
# "discarded": self.players[playerid].discarded,
# "id":self.players[playerid].id,

class Config:
    def __init__(self):
        try:
            with open('./config.json', 'r', encoding='utf-8') as f:
                self.config = json.load(f)
                print("✅ 配置文件已加载")
        except (FileNotFoundError, json.JSONDecodeError):
            print("配置文件未找到或格式错误，将创建新的配置文件。")
            self.config = self.create_new_config()
        
        self.server_list = list(self.config.get('server list', {}).keys())
        self.name_list = list(self.config.get('name list', {}).keys())
    def create_new_config(self):
        name = self.input_name()
        ip = self.input_ip()
        logsl = self.input_num("请输入日志显示长度 (例如: 10)")
        refresh = self.input_num("请输入刷新率 (例如: 30 FPS, 输入 30)")
        config = {
            'default': {'name': name, 'server': ip},
            'name list': {name: [0, 0]},
            'server list': {ip: [0, 0]},
            "logs length": logsl,
            "refresh delay": 1.0 / refresh if refresh > 0 else 0.033
        }
        self.save_config(config)
        return config
    def save_config(self, config_data):
        with open('./config.json', 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)
        print("✅ 配置文件已保存")
    def input_num(self, prompt):
        while True:
            try:
                num = int(input(f"{prompt} >> "))
                return num
            except ValueError:
                print("❌ 请输入一个有效的数字。")
    def input_name(self):
        while True:
            name = input("请输入您的用户名 >> ").strip()
            if name: return name
            print("❌ 用户名不能为空")
    def input_ip(self):
        while True:
            ip = input("请输入服务器地址 (例如: localhost:5000) >> ").strip()
            if not ip:
                print("❌ 服务器地址不能为空")
                continue
            
            url = f"http://{ip}" if not ip.startswith(('http://', 'https://')) else ip
            try:
                requests.get(url, timeout=3)
                print("✅ 连接成功")
                return url
            except requests.exceptions.RequestException:
                print(f"❌ 无法连接到服务器: {url}")
    def list_items(self, items, title):
        print(f"--- {title} ---")
        if not items:
            print("无记录。")
            return
        print(f"{'序号':<6} | {'名称':<25} | {'胜场':<8} | {'负场':<8}")
        print("-" * 55)
        for i, (key, value) in enumerate(items.items()):
            print(f"{i+1:<6} | {key:<25} | {value[0]:<8} | {value[1]:<8}")
        print("-" * 55)
    def get_choice(self, items):
        while True:
            choice = input("请选择序号 >> ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(items):
                return list(items.keys())[int(choice) - 1]
            print("❌ 无效的选择，请重新输入")
    def modify_default(self, name, server):
        self.config['default']['name'] = name
        self.config['default']['server'] = server
        self.save_config(self.config)

# --- 打印函数 (已适配新结构) ---
def clear_screen(): os.system('cls' if os.name == 'nt' else 'clear')
def print_header(): print("=" * 60 + "\n🎮 Socket.IO 游戏大厅\n" + "=" * 60)
def print_status():
    status = "🔗 已连接" if current_user['connected'] else "❌ 未连接"
    if current_user['in_room']: status += f" | 🏠 房间: {current_room['name']}"
    print(f"状态: {status} | 用户: {current_user['name']}\n" + "-" * 60)
def print_room_list():
    if not room_list:
        print("📭 暂无房间")
        return
    print("🏠 房间列表:")
    print(f"{'序号':<4} {'房间名':<20} {'人数':<8} {'状态':<10} {'密码'}")
    print("-" * 60)
    for i, room in enumerate(room_list):
        password_icon = "🔒" if room['has_password'] else " "
        members_info = f"{room['members']}/{room['max_members']}"
        print(f"{i+1:<4} {room['name']:<20} {members_info:<8} {room['status']:<10} {password_icon}")

def print_game_view():
    public_state = current_game_state.get('public', {})
    private_state = current_game_state.get('private', {})
    
    if not public_state:
        print("正在等待游戏状态更新...")
        return
    
    my_id = private_state.get('my_id')
    all_players = public_state.get('players', [])
    current_player_idx = public_state.get('playerindex')

    print("--- 游戏桌面 ---")
    for player in all_players:
        if player.get('id') == my_id: continue

        turn_marker = "➡️" if current_player_idx == player.get('id') else "  "
        print(f"\n{turn_marker}玩家: {player.get('name', 'N/A')} (手牌: {player.get('hand_count', 0)})")
        
        locked_str = ' '.join([''.join([_replacements.get(t, t) for t in group]) for group in player.get('locked', [])])
        hands_str = '🀫' * int(player.get('hand_count', 0))
        print(f"  {player.get('name', 'N/A')} : {locked_str} {hands_str}")
        
        discard_str = ' '.join([_replacements.get(t, t) for t in player.get('discarded', [])])
        print(f"{discard_str if discard_str else ''}")

    print("\n" + "-"*20)
    joker_icon = _replacements.get(private_state.get('golden_tile', 'joker'), '🃏')
    print(f"牌墙剩余: {public_state.get('wall_count', 0)} 张 | 金牌: {joker_icon}")
    
    report = public_state.get('report')
    if report: print(f"报告: {report}")
    
    if public_state.get('status') == 'finished':
        winner_id = public_state.get('winner_id')
        winner_hands = public_state.get('winner_hands', [])
        winner_name = "荒庄"
        if winner_id is not None:
            winner_name = next((p['name'] for p in all_players if p['id'] == winner_id), "未知胜利者")
        print(f"🎉 游戏结束! 结果: {winner_name} | 胜利者手牌: {winner_hands}")
    print("-" * 20)
    
    print_game_deck()

def print_game_deck():
    """
    (已重构) 打印玩家自己的手牌、新牌、明牌以及可执行的操作菜单。
    """
    global displayed_actions
    displayed_actions.clear() # 每次刷新时清空旧的操作

    private_state = current_game_state.get('private', {})
    public_state = current_game_state.get('public', {})

    my_id = private_state.get('my_id')
    if my_id is None: return

    my_player_data = next((p for p in public_state.get('players', []) if p.get('id') == my_id), None)
    if not my_player_data: return

    discarded = private_state.get('discarded', [])
    discarded_display = ' '.join([_replacements.get(t, t) for t in discarded])
    print(f"已打出的牌: {discarded_display if discarded_display else '无'}")

    turn_marker = "➡️" if public_state.get('playerindex') == my_id else "  "
    print(f"\n{turn_marker}你的手牌 ({my_player_data.get('name', 'Me')}):")

    hand = private_state.get('hands', [])
    new_tile = private_state.get('new')

    if hand is None: hand = []

    hand_display = ' '.join([_replacements.get(t, '?') for t in hand])
    new_display = _replacements.get(new_tile, '?') if new_tile else ''
    hand_indices = ' '.join([f"{i+1:<2}" for i in range(len(hand))])

    print(f"牌:  {hand_display}  {new_display}")
    print(f"序号: {hand_indices}")

    if new_tile:
        print(f"\n新摸到的牌: {_replacements.get(new_tile, '?')} (可输入 'd' 直接打出)")

    my_locked_str = ' '.join([''.join([_replacements.get(t, t) for t in group]) for group in private_state.get('locked', [])])
    print(f"  明牌: {my_locked_str if my_locked_str else '无'}")
    
    # --- 核心修改：生成带序号的操作菜单 ---
    actions = private_state.get('actions', {})
    if actions:
        print("\n可执行的操作:")
        action_idx = 1
        
        # 选项1: 过
        displayed_actions.append({'action': 'pass'})
        print(f"  {action_idx}: 过 (Pass)")
        action_idx += 1

        # 检查并添加其他操作
        if actions.get('hu'):
            displayed_actions.append({'action': 'hu'})
            print(f"  {action_idx}: 胡 (Hu)")
            action_idx += 1
        if actions.get('kong'):
            displayed_actions.append({'action': 'kong'})
            print(f"  {action_idx}: 杠 (Kong)")
            action_idx += 1
        if actions.get('pong'):
            displayed_actions.append({'action': 'pong'})
            print(f"  {action_idx}: 碰 (Pong)")
            action_idx += 1
        
        # 为每一种“吃”的组合创建一个选项
        if actions.get('chow'):
            for chow_pair in actions['chow']:
                pair_str = ' '.join([_replacements.get(t, t) for t in chow_pair])
                displayed_actions.append({'action': 'chow', 'tiles': list(chow_pair)})
                print(f"  {action_idx}: 吃 (Chow) with {pair_str}")
                action_idx += 1

def print_room_info():
    if not current_user['in_room']: return
    if current_room.get('status') in ['playing', 'finished']:
        print_game_view()
        return

    print(f"👑 房主: {current_room.get('owner', 'N/A')}")
    print("\n👥 成员列表:")
    for member_info in current_room.get('members', {}).values():
        ready_status = "✅" if member_info.get('ready') else "⏳"
        owner_mark = "👑" if member_info['name'] == current_room.get('owner') else "  "
        print(f"  {owner_mark} {ready_status} {member_info.get('name', 'N/A')}")
    if current_room['logs']:
        print("\n📝 日志:")
        for log in current_room['logs']: print(f"  {log}")

def print_chat_messages():
    if not current_room['messages']: return
    print("\n💬 聊天记录:")
    for msg in current_room['messages'][-config.config.get("logs length", 5):]:
        print(f"  {msg.get('sender', '??')}: {msg.get('message', '')}")

def print_menu():
    """打印可用命令菜单。"""
    print("\n📋 可用命令:")
    if not current_user['connected']:
        print("  connect [姓名序号] [服务器序号] - 连接服务器 (e.g., c 1 1)")
        print("  quit - 退出程序")
        config.list_items(config.config.get('name list',{}), "可用名称")
        config.list_items(config.config.get('server list',{}), "可用服务器")
    elif not current_user['in_room']:
        print("  list - 刷新房间列表\n  create - 创建房间\n  join <房号> [密码] - 加入房间\n  disconnect - 断开连接\n  quit - 退出")
    elif current_room.get('status') == 'playing':
        # --- 核心修改：根据有无待选操作，显示不同提示 ---
        if displayed_actions:
            print("  a <序号> - 执行一个操作 (例如: a 1 选择'过')")
        print("  d <序号> - 打出一张牌 (输入 'd' 打出新摸的牌)")
        print("  leave - 离开房间")
    else: # 等待或结束状态
        print("  chat <消息> - 发送聊天\n  ready - 切换准备状态\n  rules <JSON> - 修改规则(房主)\n  leave - 离开房间\n  quit - 退出")

# --- Socket.IO 事件处理 (已完全重构) ---

@sio.event
def join_room_result(data):
    """加入房间成功后，重置游戏状态"""
    if data['success']:
        print(f"\n✅ {data['message']}")
        current_user.update({'in_room': True, 'room_id': data.get('id')})
        global current_game_state
        current_game_state = {'public': {}, 'private': {}} # 重置为初始结构
    else:
        print(f"\n❌ {data['message']}")
    
@sio.event
def game_initialized(data):
    """收到游戏初始化信息，只更新 private 部分"""
    current_game_state['private']['my_id'] = data.get('my_id')
    current_game_state['private']['golden_tile'] = data.get('golden_tile')
    
    my_id = data.get('my_id')
    seat_names = ["东", "南", "西", "北"]
    my_seat = seat_names[my_id] if my_id is not None and my_id < 4 else f"座位{my_id}"
    
    print("\n" + "="*20 + f"\n      🎉 游戏开始！🎉\n  你的座位: 【{my_seat}】\n  本局金牌: 【{_replacements.get(data.get('golden_tile'), data.get('golden_tile'))}】\n" + "="*20)
    refresh_display()

@sio.event
def game_state_update(data):
    """收到公共状态，完全替换 public 部分"""
    current_game_state['public'] = data
    current_room['status'] = data.get('status', current_room['status'])
    refresh_display()

@sio.event
def private_state_update(data):
    """收到私有状态，完全替换 private 部分"""
    # 同时保留从 game_initialized 获得的初始信息
    data['my_id'] = current_game_state['private'].get('my_id')
    data['golden_tile'] = current_game_state['private'].get('golden_tile')
    current_game_state['private'] = data
    refresh_display()

# --- 其他事件和函数 (无变化) ---
@sio.event
def connect():
    print("\n✅ 成功连接到服务器!")
    sio.emit('join_server', {'name': current_user['name']})
@sio.event
def disconnect():
    print("\n❌ 与服务器的连接已断开")
    current_user.update({'connected': False, 'in_room': False})
    room_list.clear()
@sio.event
def connect_error(data): print(f"\n❌ 连接错误: {data}")
@sio.event
def connection_rejected(data): print(f"\n❌ 连接被拒绝: {data.get('reason', '未知原因')}")
@sio.event
def join_server_result(data):
    if data['success']:
        print(f"\n✅ {data['message']}")
        current_user['connected'] = True
        global room_list
        room_list = data.get('room_list', [])
    else:
        print(f"\n❌ {data['message']}")
        sio.disconnect()
    refresh_display()
@sio.event
def room_list_update(data):
    global room_list
    room_list = data
    if not current_user['in_room']: refresh_display()
@sio.event
def create_room_result(data):
    if data['success']:
        print(f"\n✅ {data['message']}")
        sio.emit('join_room', {'room_id': data['room_id'], 'password': data.get('password', '')})
    else:
        print(f"\n❌ {data['message']}")
@sio.event
def room_state_update(data):
    current_room.update(data)
    log = data.get('log')
    if log:
        current_room['logs'].append(log)
        max_logs = config.config.get("logs length", 10)
        current_room['logs'] = current_room['logs'][-max_logs:]
    if current_user['in_room']:
        refresh_display()
@sio.event
def your_turn_to_discard(data):
    print(f"\n🔔 {data.get('message', '轮到你出牌了！')}")
@sio.event
def new_tile_drawn(data):
    tile = data.get('tile', '?')
    print(f"\n🀄 你摸到了: {_replacements.get(tile, tile)}")
@sio.event
def game_action_result(data):
    msg_type = "✅" if data.get('success') else "❌"
    print(f"\n{msg_type} {data.get('message', '收到服务器响应')}")
@sio.event
def room_deleted(data):
    print(f"\n🏠 {data['message']}")
    current_user.update({'in_room': False, 'room_id': None, 'is_ready': False})
    global current_room, current_game_state
    current_room = {'name': 'Unknown', 'id': None, 'owner': 'Unknown', 'game': None, 'members': {}, 'messages': [], 'rules': {}, 'status': '', 'logs': []}
    current_game_state = {'public': {}, 'private': {}}
    refresh_display()
@sio.event
def leave_room_result(data):
    if data['success']:
        print(f"\n✅ {data['message']}")
        current_user.update({'in_room': False, 'room_id': None, 'is_ready': False})
        global current_room, current_game_state
        current_room = {'name': 'Unknown', 'id': None, 'owner': 'Unknown', 'game': None, 'members': {}, 'messages': [], 'rules': {}, 'status': '', 'logs': []}
        current_game_state = {'public': {}, 'private': {}}
        refresh_display()
@sio.event
def chat_message(data):
    current_room['messages'].append(data)
    if current_user['in_room']: refresh_display()
@sio.event
def refresh_countdown(data):
    # 本地只有倒计时，仅做提醒，不影响游戏逻辑
    timeout = data.get('timeout', 0)
    print(f"\n⏳ 剩余出牌时间: {timeout} 秒")

def refresh_display():
    global last_refresh_time
    refresh_delay = config.config.get('refresh delay', 0.033)
    current_time = time.time()
    if current_time - last_refresh_time < refresh_delay:
        return
    last_refresh_time = current_time
    clear_screen()
    print_header()
    print_status()
    if current_user['in_room']:
        print_room_info()
        print_chat_messages()
    else:
        print_room_list()
    print_menu()
def handle_command(command):
    parts = command.strip().split()
    if not parts: 
        return
    cmd = parts[0].lower()

    if cmd in ('quit', 'q'):
        should_exit.set()
        if current_user['connected']: sio.disconnect()
        print("👋 再见!")
        return

    if not current_user['connected']:
        if cmd in ('connect', 'c'):
            try:
                name_idx = int(parts[1]) - 1 if len(parts) > 1 else -1
                server_idx = int(parts[2]) - 1 if len(parts) > 2 else -1
                name = config.name_list[name_idx] if 0 <= name_idx < len(config.name_list) else config.config['default']['name']
                server = config.server_list[server_idx] if 0 <= server_idx < len(config.server_list) else config.config['default']['server']
                current_user['name'] = name
                current_user['server'] = server
                config.modify_default(name, server)
                print(f"🔗 正在以用户 '{name}' 连接到 {server}...")
                sio.connect(server, transports=['websocket'])
            except (ValueError, IndexError):
                print("❌ 无效的序号。将使用默认配置。")
                current_user['name'] = config.config['default']['name']
                current_user['server'] = config.config['default']['server']
                sio.connect(current_user['server'], transports=['websocket'])
            except Exception as e:
                print(f"❌ 连接失败: {e}")
        else:
            print("❌ 未连接，请使用 'connect' 或 'c' 命令进行连接。")
        return

    if cmd in ('disconnect', 'dis'):
        sio.disconnect()
        return

    if not current_user['in_room']:
        if cmd == 'list': sio.emit('request_room_list', {})
        elif cmd == 'create':
            room_name = input("请输入房间名: ").strip()
            if room_name: sio.emit('create_room', {'name': room_name, 'password': input("请输入房间密码 (可选): ").strip()})
        elif cmd == 'join':
            try:
                room_index = int(parts[1]) - 1
                if 0 <= room_index < len(room_list):
                    room = room_list[room_index]
                    password = parts[2] if len(parts) > 2 else ""
                    if room['has_password'] and not password:
                        password = input("该房间需要密码，请输入: ").strip()
                    sio.emit('join_room', {'room_id': room['id'], 'password': password})
                else: print("❌ 无效的房间序号")
            except (ValueError, IndexError): print("❌ 请输入有效的房间序号 (e.g., join 1)")
        else: print(f"❌ 未知命令: {cmd}")
        return

    if current_user['in_room']:
        if cmd in ('leave', 'l'): 
            sio.emit('leave_room', {})
        elif cmd in ('chat', 'say'):
            message = ' '.join(parts[1:])
            if message: sio.emit('chat_message', {'message': message})
        
        elif current_room.get('status') == 'playing':
            # --- 核心修改：处理 a <序号> 和 d <序号> 命令 ---
            if cmd in ('a', 'action'):
                if not displayed_actions:
                    print("❌ 当前没有可供选择的操作。")
                    return
                try:
                    choice_idx = int(parts[1]) - 1
                    if 0 <= choice_idx < len(displayed_actions):
                        # 从列表中获取预先构建好的动作数据包
                        action_payload = displayed_actions[choice_idx]
                        sio.emit('game_action', action_payload)
                    else:
                        print("❌ 无效的操作序号。")
                except (ValueError, IndexError):
                    print("❌ 请输入有效的操作序号 (例如: a 1)")
                
            elif cmd in ('d', 'discard'):
                action_payload = {'action': 'discard'}
                try:
                    # 减1以匹配列表索引
                    action_payload['tileindex'] = int(parts[1]) - 1
                except (ValueError, IndexError):
                    # 如果没有提供序号 (例如只输入 'd')，则设为 None
                    action_payload['tileindex'] = None
                sio.emit('game_action', action_payload)
            else:
                print(f"❌ 游戏中未知命令: {cmd}。可用命令: a(操作), d(出牌), leave, chat。")
        
        else: # 房间处于等待或结束状态
            if cmd in ('ready', 'r'):
                current_user['is_ready'] = not current_user.get('is_ready', False)
                sio.emit('player_ready', {'ready': current_user['is_ready']})
            elif cmd == 'rules':
                try:
                    rules = json.loads(' '.join(parts[1:]))
                    sio.emit('update_room_rules', {'rules': rules})
                except json.JSONDecodeError: print("❌ 无效的JSON格式")
            else:
                print(f"❌ 房间中未知命令: {cmd}")
        return
        
    print(f"❌ 未知命令: {cmd}")
def input_thread():
    while not should_exit.is_set():
        try:
            command = input("\n>> ")
            if command:
                handle_command(command)
            refresh_display()    
        except (KeyboardInterrupt, EOFError):
            should_exit.set()
            break
        except Exception as e:
            print(f"❌ 输入处理错误: {e}")
def main():
    global config
    config = Config()
    print_menu()
    
    input_handler = threading.Thread(target=input_thread, daemon=True)
    input_handler.start()
    
    try: should_exit.wait()
    except KeyboardInterrupt: should_exit.set()
    
    print("\n🔌 客户端关闭中...")

if __name__ == '__main__':
    main()