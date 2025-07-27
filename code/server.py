import socketio
import json
import threading
import time
import uuid
from datetime import datetime
import eventlet
import mahjong
import os
import random
import logging

# 配置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# 创建Socket.IO服务器
sio = socketio.Server(cors_allowed_origins="*")
app = socketio.WSGIApp(sio)

# 全局数据存储
users = {}
rooms = {}
blacklist = set()
DEFAULT_RULES = { "max players": 4, "tiles number": 16, "golden tile": True, "golden tile number": 4, "three golden win": True, "allow seven pairs": False, "stand delay": 20, "special delay": 5 }
_replacements = {
    '1o': '🀙', '2o': '🀚', '3o': '🀛', '4o': '🀜', '5o': '🀝', '6o': '🀞', '7o': '🀟', '8o': '🀠', '9o': '🀡',
    '1t': '🀐', '2t': '🀑', '3t': '🀒', '4t': '🀓', '5t': '🀔', '6t': '🀕', '7t': '🀖', '8t': '🀗', '9t': '🀘',
    '1w': '🀇', '2w': '🀈', '3w': '🀉', '4w': '🀊', '5w': '🀋', '6w': '🀌', '7w': '🀍', '8w': '🀎', '9w': '🀏',
    'e': '🀀', 's': '🀁', 'w': '🀂', 'n': '🀃', 'b': '🀆', 'f': '🀅', 'z': '🀄', 'joker': '🃏', 'back': '🀫',
    'spring': '🀦', 'summer': '🀧', 'autumn': '🀨', 'winter': '🀩',
    'plum': '🀢', 'orchid': '🀣', 'bamboo': '🀤', 'chrysanthemum': '🀥'
}
class NotAcceptTime(Exception): pass
class AlreadyActed(Exception): pass

class mahjong_room:
    def __init__(self, name, password, id=None):
        self.name = name
        self.game = 'mahjong'
        self.log = ''
        self.id = id
        self.password = password
        self.owner = None
        self.winner = None
        self.members = {}
        self.spectators = {}
        self.status = 'waiting'
        self.game_instance = None
        self.created_time = datetime.now().isoformat()
        self.rules = { "rules": "classic", "max players": 4, "tiles number": 16, "golden tile": True, "golden tile number": 4, "three golden win": True, "allow seven pairs": False, "stand delay": 20, "special delay": 5, "items_to_remove": ['spring', 'summer', 'autumn', 'winter', 'plum', 'orchid', 'bamboo', 'chrysanthemum'] }

        # 游戏流程控制属性
        self.sid_to_player_id = {}
        self.player_id_to_sid = {}
        self.pending_claims = {}
        self.submitted_claims = {}

    # --- 房间管理方法 (未改变) ---
    def add_member(self, sid, name):
        if sid in self.members: return self.members
        sio.enter_room(sid, self.id)
        self.log = f"{datetime.now().isoformat()} {name} 加入房间"
        self.members[sid] = {'name': name, 'ready': False, 'ip': users[sid]['ip']}
        return self.members
    def remove_member(self, sid):
        if sid in self.members:
            self.log = f"{datetime.now().isoformat()} {self.members[sid]['name']} 离开房间"
            del self.members[sid]
            sio.leave_room(sid, self.id)
            return True
        return False
    def get_members(self): return list(self.members.keys())
    def get_member(self, sid): return self.members.get(sid, None)
    def is_full(self): return len(self.members) >= self.rules['max players']
    def modify_rules(self, new_rules, sid):
        self.rules.update(new_rules) # 简化规则更新
        self.log = f"{datetime.now().isoformat()} {self.members[sid]['name']} 修改了房间规则"
        print(f"✅ 房间 {self.name} 的规则已更新: {self.rules}")
        return self.rules

    # --- 游戏状态广播方法 ---
    def update_all_clients(self, log_message=None):
        """更新客户端数据"""
        if not self.game_instance: return
        public_state = self.game_instance.getgamestate()
        if log_message:
            public_state['report'] = log_message
        sio.emit('game_state_update', public_state, room=self.id)

        for p in self.game_instance.players:
            private_state = self.game_instance.getgamestate(playerid=p.id)
            player_sid = self.player_id_to_sid.get(p.id)
            if player_sid:
                sio.emit('private_state_update', private_state, room=player_sid)

    # --- 游戏核心逻辑 ---
    def start_game(self):
        """
        初始化并开始麻将游戏 (已重构，使用 game_initialized 事件)
        """
        if self.status == 'playing': return

        player_sids = list(self.members.keys())
        player_names = [self.members[sid]['name'] for sid in player_sids]
        
        self.game_instance = mahjong.MahjongServer(playersnames=player_names)
        self.status = 'playing'
        self.sid_to_player_id = {sid: i for i, sid in enumerate(player_sids)}
        self.player_id_to_sid = {i: sid for sid, i in self.sid_to_player_id.items()}

        # 1. 初始化游戏引擎（洗牌、发牌、选金）
        self.game_instance.start(dice=random.randint(2, 12))
        
        # 2. 庄家摸开局第一张牌
        dealer = self.game_instance.players[self.game_instance.playerindex]
        self.game_instance.new_tile()

        # 3. 【核心】为每个玩家单独发送初始化信息
        golden_tile = self.game_instance.golden_tile
        
        for p in self.game_instance.players:
            player_sid = self.player_id_to_sid.get(p.id)
            if player_sid:
                sio.emit('game_initialized', {
                    'my_id': p.id,
                    'golden_tile': golden_tile
                }, room=player_sid)

        # 4. 最后，广播公共状态并通知庄家出牌
        self.update_all_clients(f"游戏开始！金牌是 {_replacements.get(golden_tile, golden_tile)}。")
        self._notify_player_to_discard(dealer.id)

    def handle_player_action(self, sid, data):
        """处理所有来自客户端的游戏内动作"""
        action_type = data.get('action')
        player_id = self.sid_to_player_id.get(sid)
        if player_id is None: return

        try:
            if action_type == 'discard':
                self._handle_discard(player_id, data.get('tileindex'))
            elif action_type in ['hu', 'pong', 'kong', 'chow']:
                self._handle_claim(player_id, data)
            else:
                raise ValueError("未知的游戏操作")
        except (ValueError, NotAcceptTime, AlreadyActed) as e:
            logging.warning(f"玩家 {player_id} 操作无效: {e}")
            sio.emit('game_action_result', {'success': False, 'message': str(e)}, room=sid)

    def _handle_discard(self, player_id, tile_index):
        game = self.game_instance
        if player_id != game.playerindex: raise NotAcceptTime("现在不是你的出牌回合。")
        
        player = game.players[player_id]
        discarded_tile = player.discard(tile_index)
        if player.new:
            player.integrate_new_tile()
        player.sort_hands(game.sort_rule)
        
        # 统一调用更新函数
        self.update_all_clients(f"玩家 {player.name} 打出了: {_replacements.get(discarded_tile, discarded_tile)}")

        game.checkactions(discarded_tile)
        self.pending_claims = game.pending_claims
        self.submitted_claims = {}

        if self.pending_claims:
            self.update_all_clients(f"玩家 {player.name} 出牌后，等待其他玩家响应...")
            sio.start_background_task(self._process_claims_after_delay) # 不会倒计时提醒客户端，只有在超时后才会处理
        else:
            sio.start_background_task(self._transition_to_next_turn)

    def _handle_claim(self, player_id, data):
        """接收并暂存玩家的响应动作 (微调)"""
        action_type = data['action']
        if not self.pending_claims or action_type not in self.pending_claims or player_id not in self.pending_claims[action_type]:
            raise NotAcceptTime("你当前不能执行此操作。")
        if player_id in self.submitted_claims: raise AlreadyActed("你已经提交过操作了。")

        claim_data = action_type
        if action_type == 'chow':
            chow_pair = tuple(sorted(data.get('tiles', [])))
            # 从出牌者的弃牌堆找到那张牌来验证
            discarding_player = self.game_instance.players[self.game_instance.playerindex]
            last_discarded_tile = discarding_player.discarded[-1]
            
            possible_chows = self.game_instance.players[player_id].can_chow(
                last_discarded_tile,
                self.game_instance.sort_rule
            )
            if chow_pair not in possible_chows: raise ValueError("无效的吃牌组合。")
            claim_data = ('chow', chow_pair)

        self.submitted_claims[player_id] = claim_data
        logging.info(f"玩家 {self.game_instance.players[player_id].name} 提交了操作: {action_type}")
        sio.emit('game_action_result', {'success': True, 'message': '操作已提交，等待其他玩家...'}, room=self.player_id_to_sid[player_id])

    def _process_claims_after_delay(self):
        """处理特殊动作"""
        delay = self.rules.get('special delay', 5)
        sio.sleep(delay)
        game = self.game_instance
        
        action_type = None # 捕获动作类型
        if self.submitted_claims:
            # 简化获取action_type的逻辑
            first_claim = list(self.submitted_claims.values())[0]
            action_type = first_claim[0] if isinstance(first_claim, tuple) else first_claim

        actor_id = game.processactions(self.submitted_claims)
        self.pending_claims = {}
        self.submitted_claims = {}

        for player in game.players:
            player.actions = {} # 清空玩家的动作列表
        
        if game.status == 'finished':
            self.end_game_as_draw("游戏结束") # 使用一个统一的结束函数
            return

        if actor_id is not None:
            game.turntonext(actor_id=actor_id)
            actor_player = game.players[actor_id]
            if action_type == 'kong':
                game.new_tile()

            self.update_all_clients(f"玩家 {actor_player.name} 执行了 {action_type} 操作。")
            if not actor_player.hands:
                self.end_game_as_draw("荒庄(有玩家无牌可打)")
                return
            self._notify_player_to_discard(actor_id)
        else:
            if game.status == 'playing':
                 self._transition_to_next_turn()      

    def _transition_to_next_turn(self):
        game = self.game_instance
        if not game.wall:
            self.end_game_as_draw("牌墙已空，游戏荒庄！")
            return

        game.turntonext()
        next_player_id = game.playerindex
        next_player = game.players[next_player_id]
        newly_drawn_tile = game.new_tile()
        
        if not newly_drawn_tile:
            self.end_game_as_draw("牌墙已空，游戏荒庄！")
            return
            
        logging.info(f"玩家 {next_player.name} 摸到了: {newly_drawn_tile}")
        
        if next_player.can_hu(newly_drawn_tile, game.sort_rule, game.gamerule):
            game.pending_claims = {'hu': {next_player_id: 0}}
            self.update_all_clients(f"轮到玩家 {next_player.name} 摸牌。")
            self._notify_player_to_discard(next_player_id, can_hu=True)
            return

        self.update_all_clients(f"轮到玩家 {next_player.name} 摸牌。")
        self._notify_player_to_discard(next_player_id)

    def _start_discard_timer(self, timed_player_id, timeout):
        """为出牌玩家启动倒计时"""
        sio.sleep(timeout)
        if self.status == 'playing' and self.game_instance.playerindex == timed_player_id:
            logging.info(f"⏰ 玩家 {self.game_instance.players[timed_player_id].name} 出牌超时，系统自动出牌。")
            try:
                # 自动打出新摸的牌 (tile_index=None)
                self._handle_discard(timed_player_id, None)
            except Exception as e:
                logging.error(f"自动出牌时发生错误: {e}")
        
    def _notify_player_to_discard(self, player_id, can_hu=False):
        """通知玩家出牌, 未来会添加掉线重连逻辑，掉线或者托管的玩家的 timeout 为 1s"""
        player_sid = self.player_id_to_sid.get(player_id)
        if player_sid:
            timeout = self.rules.get('stand delay', 20)
            message = f"请在 {timeout} 秒内出牌"
            if can_hu: message += "，或者选择自摸胡牌"
            sio.emit('your_turn_to_discard', {'message': message}, room=player_sid)
            sio.emit('refresh_countdown', {'timeout': timeout}, room=player_sid)    # 提醒客户端倒计时
            sio.start_background_task(self._start_discard_timer, player_id, timeout)

    def end_game_as_draw(self, reason):
        if self.status == 'finished': return
        logging.info(reason)
        
        winner_name = "荒庄"
        if self.game_instance.winner_id is not None:
             winner_name = self.game_instance.players[self.game_instance.winner_id].name
        
        self.game_instance.endgame(reason=reason)
        self.status = 'finished'
        self.update_all_clients(f"游戏结束！{reason}。胜利者: {winner_name}")


# --- 全局服务器事件 (大部分未改变) ---
def get_room_list():
    return [{'id': r.id, 'name': r.name, 'game': r.game, 'owner': r.owner, 'members': len(r.members), 'max_members': r.rules['max players'], 'has_password': bool(r.password), 'status': r.status} for r in rooms.values()]
def broadcast_room_state(room_id, log=None):
    if room_id not in rooms: return
    if log: rooms[room_id].log = log
    room = rooms[room_id]
    room_state = {'game': room.game, 'name': room.name, 'id': room.id, 'owner': room.owner, 'members': room.members, 'rules': room.rules, 'status': room.status, 'log': room.log}
    sio.emit('room_state_update', room_state, room=room_id)

@sio.event
def connect(sid, environ):
    client_ip = environ.get('REMOTE_ADDR', 'unknown')
    logging.info(f"🔗 客户端连接: {sid} from {client_ip}")
    users[sid] = {'ip': client_ip, 'name': '', 'room_id': '', 'status': 'offline'}
@sio.event
def disconnect(sid):
    logging.info(f"🔌 客户端断开: {sid}")
    if sid in users:
        if users[sid].get('room_id'):
            handle_leave_room(sid, users[sid]['room_id'])
        del users[sid]
@sio.event
def join_server(sid, data):
    name = data.get('name', '').strip()
    if not name:
        sio.emit('join_server_result', {'success': False, 'message': '用户名不能为空'}, room=sid)
        return
    users[sid]['name'] = name; users[sid]['status'] = 'online'
    sio.emit('join_server_result', {'success': True, 'message': '连接成功', 'room_list': get_room_list()}, room=sid)
    logging.info(f"✅ 用户 {name} 成功加入服务器")
@sio.event
def create_room(sid, data):
    print(f"用户 {sid} 请求创建房间: {data}")
    room_name = data.get('name', '').strip()
    if not room_name:
        sio.emit('create_room_result', {'success': False, 'message': '房间名不能为空'}, room=sid)
        return
    room_id = str(uuid.uuid4())
    rooms[room_id] = mahjong_room(room_name, data.get('password', ''), room_id)
    rooms[room_id].owner = users[sid]['name']
    sio.emit('create_room_result', {'success': True, 'message': '房间创建成功', 'room_id': room_id, 'password': data.get('password', '')}, room=sid)
    sio.emit('room_list_update', get_room_list())
    logging.info(f"🏠 用户 {users[sid]['name']} 创建了房间: {room_name}")
@sio.event
def join_room(sid, data):
    print(f"用户 {sid} 请求加入房间: {data}")
    room_id = data.get('room_id')
    password = data.get('password', '')
    if room_id not in rooms:
        sio.emit('join_room_result', {'success': False, 'message': '房间不存在'}, room=sid)
        return
    room = rooms[room_id]
    if room.is_full():
        sio.emit('join_room_result', {'success': False, 'message': '房间已满'}, room=sid)
        return
    if room.password and room.password != password:
        sio.emit('join_room_result', {'success': False, 'message': '密码错误'}, room=sid)
        return
    room.add_member(sid, users[sid]['name'])
    users[sid]['room_id'] = room_id; users[sid]['status'] = 'in_room'
    sio.emit('join_room_result', {'success': True, 'message': '成功加入房间', 'id': room_id}, room=sid)
    broadcast_room_state(room_id)
    sio.emit('room_list_update', get_room_list())
    logging.info(f"🚪 用户 {users[sid]['name']} 加入了房间: {room.name}")
def handle_leave_room(sid, room_id):
    if room_id not in rooms: return
    user_name = users[sid]['name']
    room = rooms[room_id]
    room.remove_member(sid)
    if room.owner == user_name:
        sio.emit('room_deleted', {'message': '房主离开，房间已解散'}, room=room_id)
        del rooms[room_id]
        logging.info(f"🏠 房间 {room.name} 已删除")
    else:
        broadcast_room_state(room_id, f"{datetime.now().isoformat()} {user_name} 离开房间")
    users[sid]['room_id'] = None; users[sid]['status'] = 'online'
    sio.emit('room_list_update', get_room_list())
@sio.event
def leave_room(sid, data):
    if sid in users and users[sid].get('room_id'):
        handle_leave_room(sid, users[sid]['room_id'])
        sio.emit('leave_room_result', {'success': True, 'message': '已离开房间'}, room=sid)
@sio.event
def chat_message(sid, data):
    room_id = users[sid].get('room_id')
    message = data.get('message', '').strip()
    if not room_id or not message: return
    chat_data = {'sender': users[sid]['name'], 'message': message, 'timestamp': datetime.now().isoformat()}
    sio.emit('chat_message', chat_data, room=room_id)
@sio.event
def player_ready(sid, data):
    room_id = users[sid].get('room_id')
    if not room_id: return
    room = rooms[room_id]
    room.members[sid]['ready'] = data.get('ready', False)
    room.log = f"{datetime.now().isoformat()} {room.members[sid]['name']} {'准备' if room.members[sid]['ready'] else '取消准备'}"
    broadcast_room_state(room_id)
    if sum(1 for m in room.members.values() if m['ready']) == room.rules['max players']:
        sio.start_background_task(start_game_countdown, room_id)
def start_game_countdown(room_id):
    """游戏开始倒计时"""
    if room_id not in rooms: return
    room = rooms[room_id]
    if room.status == 'playing': return
    
    logging.info(f"房间 {room.name} 准备开始倒计时...")
    for i in range(3, 0, -1):
        broadcast_room_state(room_id, f"所有玩家已准备，游戏还有 {i} 秒开始")
        sio.sleep(1)
    
    # 再次检查状态
    if len(room.members) != room.rules['max players'] or not all(m['ready'] for m in room.members.values()):
        broadcast_room_state(room_id, "有玩家取消准备或离开，游戏开始已取消")
        return
    
    room.start_game()
    broadcast_room_state(room_id, "游戏开始！")

@sio.event
def game_action(sid, data):
    """游戏操作的统一入口"""
    if sid not in users: return
    room_id = users[sid].get('room_id')
    if not room_id or room_id not in rooms: return
    room = rooms[room_id]
    if room.status != 'playing':
        sio.emit('game_action_result', {'success': False, 'message': '游戏未开始'}, room=sid)
        return
    # 将动作全权委托给房间实例处理
    room.handle_player_action(sid, data)

if __name__ == '__main__':
    print("🚀 Socket.IO 服务器启动中...")
    print("📡 监听端口: 5000")
    eventlet.wsgi.server(eventlet.listen(('127.0.0.1', 5000)), app)