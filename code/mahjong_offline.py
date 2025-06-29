import random
from collections import Counter

class mahjong_players:
    def __init__(self, user_id, name, rules_def, tiles=None):
        self.user_id = user_id
        self.name = f"玩家 {user_id + 1} ({name})"
        self.tiles = tiles if tiles is not None else []
        self.rules = rules_def  # 这是麻将牌的排序和数值定义
        self.new_tile = None
        self.locked_tiles = []

    def sort_tiles(self):
        self.tiles.sort(key=lambda t: self.rules.get(t, -1))

    def get_player_input(self, game_replacements, can_zimo=False):
        """
        获取玩家输入。can_zimo标志位用于判断是否显示“自摸”选项。
        """
        while True:
            hand_str = ' '.join(game_replacements.get(t, t) for t in self.tiles)
            print(f"\n--- {self.name} 的回合 ---")
            
            locked_str = ' '.join(''.join(game_replacements.get(t,t) for t in meld) for meld in self.locked_tiles)
            print(f"明牌: {locked_str}")
            print(f"手牌: {hand_str}")

            if self.new_tile:
                print(f"新摸的牌是: {game_replacements.get(self.new_tile, self.new_tile)}")
            
            numbered_hand = [f"({i+1}) {game_replacements.get(t, t)}" for i, t in enumerate(self.tiles)]
            print(" ".join(numbered_hand))

            prompt = f"请选择要打出的牌的序号 (1-{len(self.tiles)})"
            if can_zimo:
                prompt += "，或输入'hu'来宣布自摸: "
            else:
                prompt += ": "
                
            choice = input(prompt).lower()

            if choice == 'hu' and can_zimo:
                return 'hu' # 返回一个特殊字符串表示自摸

            try:
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < len(self.tiles):
                    return choice_idx # 返回要打的牌的索引
                else:
                    print(f"输入无效，请输入1到{len(self.tiles)}之间的数字。")
            except ValueError:
                print("输入无效，请输入正确的指令。")

    def discard_tile(self, tile_index):
        discarded = self.tiles.pop(tile_index)
        self.new_tile = None
        # 注意：此处不排序，因为出牌后手牌是未排序状态，等待下次摸牌再排序
        return discarded

    # ... can_pong, can_kong, can_chow 等函数保持不变 ...
    def can_pong(self, tile):
        return self.tiles.count(tile) >= 2

    def can_kong(self, tile):
        return self.tiles.count(tile) >= 3
    
    # can_chow 保持不变
    def can_chow(self, tile):
        if 'joker' in tile or tile[0] in 'eswnbfz':
            return []
        possible_chows = []
        tile_val = self.rules.get(tile)
        if tile_val is None: return []
        tile_suit = tile[-1]
        # (tile-2, tile-1) + tile
        t1_val, t2_val = tile_val - 2, tile_val - 1
        c1 = next((t for t, v in self.rules.items() if v == t1_val and t[-1] == tile_suit), None)
        c2 = next((t for t, v in self.rules.items() if v == t2_val and t[-1] == tile_suit), None)
        if c1 in self.tiles and c2 in self.tiles: possible_chows.append(tuple(sorted([c1, c2], key=lambda t: self.rules.get(t))))
        # (tile-1, tile+1) + tile
        t1_val, t2_val = tile_val - 1, tile_val + 1
        c1 = next((t for t, v in self.rules.items() if v == t1_val and t[-1] == tile_suit), None)
        c2 = next((t for t, v in self.rules.items() if v == t2_val and t[-1] == tile_suit), None)
        if c1 in self.tiles and c2 in self.tiles: possible_chows.append(tuple(sorted([c1, c2], key=lambda t: self.rules.get(t))))
        # tile + (tile+1, tile+2)
        t1_val, t2_val = tile_val + 1, tile_val + 2
        c1 = next((t for t, v in self.rules.items() if v == t1_val and t[-1] == tile_suit), None)
        c2 = next((t for t, v in self.rules.items() if v == t2_val and t[-1] == tile_suit), None)
        if c1 in self.tiles and c2 in self.tiles: possible_chows.append(tuple(sorted([c1, c2], key=lambda t: self.rules.get(t))))
        return list(set(possible_chows))

    def can_hu(self, tile=None, game_rules=None):
        if game_rules is None: game_rules = {}
        temp_hand = self.tiles + ([tile] if tile else [])
        counts = Counter(temp_hand)
        joker_count = counts.pop('joker', 0)
        
        if game_rules.get('three_jokers_win', False) and joker_count >= 3:
            return True

        hand_size = sum(counts.values()) + joker_count
        
        if game_rules.get('allow_all_pairs', True):
             # 对子胡的总数必须是偶数
            if hand_size % 2 == 0 and self._check_all_pairs(counts.copy(), joker_count):
                return True
        
        if (hand_size - 2) % 3 != 0:
            return False

        sorted_tiles = sorted(counts.keys(), key=lambda t: self.rules.get(t, -1))
        for pair_tile in sorted_tiles:
            if counts[pair_tile] >= 2:
                remaining_counts = counts.copy()
                remaining_counts[pair_tile] -= 2
                if remaining_counts[pair_tile] == 0: del remaining_counts[pair_tile]
                if self._can_form_all_melds(remaining_counts, joker_count):
                    return True
            if counts[pair_tile] >= 1 and joker_count > 0:
                remaining_counts = counts.copy()
                del remaining_counts[pair_tile]
                if self._can_form_all_melds(remaining_counts, joker_count - 1):
                    return True
        return False
    def perform_pong(self, tile):
        """执行碰牌操作"""
        print(f"{self.name} 执行 碰!")
        # 创建碰的明牌组
        meld = sorted([tile, tile, tile], key=lambda t: self.rules.get(t))
        self.locked_tiles.append(meld)
        # 从手牌中移除两张
        self.tiles.remove(tile)
        self.tiles.remove(tile)

    def perform_kong(self, tile):
        """执行杠牌操作"""
        print(f"{self.name} 执行 杠!")
        meld = sorted([tile, tile, tile, tile], key=lambda t: self.rules.get(t))
        self.locked_tiles.append(meld)
        # 从手牌中移除三张
        for _ in range(3):
            self.tiles.remove(tile)

    def perform_chow(self, tile, chow_pair):
        """执行吃牌操作"""
        print(f"{self.name} 执行 吃!")
        meld = sorted(list(chow_pair) + [tile], key=lambda t: self.rules.get(t))
        self.locked_tiles.append(meld)
        # 从手牌中移除吃掉的组合
        for card in chow_pair:
            self.tiles.remove(card)

    def _check_all_pairs(self, counts, joker_count=0):
        holes = sum(count % 2 for count in counts.values())
        return joker_count >= holes and (joker_count - holes) % 2 == 0
    
    # _can_form_all_melds 保持不变...
    def _can_form_all_melds(self, counts, joker_count):
        if not any(counts.values()):
            return True
        first_tile = sorted(counts.keys(), key=lambda t: self.rules.get(t, -1))[0]
        # 刻子
        if counts[first_tile] >= 3:
            new_counts = counts.copy(); new_counts[first_tile] -= 3
            if new_counts[first_tile] == 0: del new_counts[first_tile]
            if self._can_form_all_melds(new_counts, joker_count): return True
        if counts[first_tile] >= 2 and joker_count >= 1:
            new_counts = counts.copy(); new_counts[first_tile] -= 2
            if new_counts[first_tile] == 0: del new_counts[first_tile]
            if self._can_form_all_melds(new_counts, joker_count - 1): return True
        if counts[first_tile] >= 1 and joker_count >= 2:
            new_counts = counts.copy(); del new_counts[first_tile]
            if self._can_form_all_melds(new_counts, joker_count - 2): return True
        # 顺子
        tile_val = self.rules.get(first_tile); tile_suit = first_tile[-1]
        # 筒顺子
        if tile_suit in 'otw' and first_tile[0] not in '89':
            t2_name = next((k for k,v in self.rules.items() if v == tile_val + 1 and k[-1] == tile_suit), None)
            t3_name = next((k for k,v in self.rules.items() if v == tile_val + 2 and k[-1] == tile_suit), None)
            if t2_name and t3_name:
                jokers_needed = (1 if counts.get(t2_name, 0) == 0 else 0) + (1 if counts.get(t3_name, 0) == 0 else 0)
                if joker_count >= jokers_needed:
                    new_counts = counts.copy(); new_counts[first_tile] -= 1
                    if new_counts[first_tile] == 0: del new_counts[first_tile]
                    if counts.get(t2_name, 0) > 0: new_counts[t2_name] -= 1; 
                    if new_counts.get(t2_name) == 0: del new_counts[t2_name]
                    if counts.get(t3_name, 0) > 0: new_counts[t3_name] -= 1; 
                    if new_counts.get(t3_name) == 0: del new_counts[t3_name]
                    if self._can_form_all_melds(new_counts, joker_count - jokers_needed): return True             
        return False

class mahjong_game:
    def __init__(self):
        self.players = []
        self.discarded_pile = []
        self.current_player_index = 0
        self.game_over = False
        self.wall = []
        self.game_rules = {}
        self.tile_definitions = {
            '1o': 2, '2o': 3, '3o': 4, '4o': 5, '5o': 6, '6o': 7, '7o': 8, '8o': 9, '9o': 10,
            '1t': 12, '2t': 13, '3t': 14, '4t': 15, '5t': 16, '6t': 17, '7t': 18, '8t': 19, '9t': 20,
            '1w': 22, '2w': 23, '3w': 24, '4w': 25, '5w': 26, '6w': 27, '7w': 28, '8w': 29, '9w': 30,
            'e': 32, 's': 34, 'w': 36, 'n': 38, 'b': 42, 'f': 44, 'z': 46,
            'joker': 0, 'back': 99
        }
        self._replacements = {
            '1o': '🀙', '2o': '🀚', '3o': '🀛', '4o': '🀜', '5o': '🀝', '6o': '🀞', '7o': '🀟', '8o': '🀠', '9o': '🀡',
            '1t': '🀐', '2t': '🀑', '3t': '🀒', '4t': '🀓', '5t': '🀔', '6t': '🀕', '7t': '🀖', '8t': '🀗', '9t': '🀘',
            '1w': '🀇', '2w': '🀈', '3w': '🀉', '4w': '🀊', '5w': '🀋', '6w': '🀌', '7w': '🀍', '8w': '🀎', '9w': '🀏',
            'e': '🀀', 's': '🀁', 'w': '🀂', 'n': '🀃', 'b': '🀆', 'f': '🀅', 'z': '🀄', 'joker': '🃏', 'back': '🀫'
        }

    def _apply_rules_and_setup_wall(self):
        """
        [重构] 根据游戏规则准备牌墙。替代旧的Fuzhou_rules。
        """
        print("--- 应用游戏规则并准备牌墙 ---")
        
        # 根据规则移除不需要的牌种
        items_to_remove = self.game_rules.get('items_to_remove', {'back'})
        self.tile_definitions = {name: val for name, val in self.tile_definitions.items() if name not in items_to_remove}

        # 洗牌
        main_tiles = [name for name, val in self.tile_definitions.items() if val < 50 and name != 'joker']
        self.wall = [name for name in main_tiles for _ in range(4)]
        random.shuffle(self.wall)
        print(f"牌墙洗牌完成，共 {len(self.wall)} 张牌。")

        # 根据规则处理金牌
        if self.game_rules.get('has_joker', True):
            gold_dice = random.randint(2, 12)
            gold_tile_name = self.wall[-gold_dice]
            print("翻出的金牌是:", self._replacements.get(gold_tile_name, gold_tile_name))
            self.wall = ['joker' if tile == gold_tile_name else tile for tile in self.wall]
            joker_count = self.wall.count('joker')
            # 确保不多于规则允许的金牌数
            max_jokers = self.game_rules.get('joker_count', 4)
            while self.wall.count('joker') > max_jokers:
                self.wall.remove('joker')
            print(f"牌墙中共有 {self.wall.count('joker')} 张金牌 (Joker)。")

    def deal_tiles(self):
        print("\n--- 开始发牌 ---")
        tiles_per_player = self.game_rules.get('tiles_per_player', 13)
        for player in self.players:
            player.tiles = self.wall[:tiles_per_player]
            self.wall = self.wall[tiles_per_player:]
            player.sort_tiles()
            hand_str = ' '.join(self._replacements.get(t, t) for t in player.tiles)
            print(f"{player.name} 的初始手牌: {hand_str}")
        print(f"\n牌墙剩余: {len(self.wall)} 张")
        print("牌墙：", ' '.join(self._replacements.get(t, t) for t in self.wall), "...")

    def draw_tile(self, player):
        if not self.wall:
            return None
        new_tile = self.wall.pop(0)
        player.new_tile = new_tile
        player.tiles.append(new_tile)
        player.sort_tiles()
        return new_tile

    def check_for_claims_and_act(self, discarded_tile, discarder_index):
        """
        [已整合胡牌判断] 检查其他玩家的操作。
        """
        possible_actions = []
        next_player_index = (discarder_index + 1) % 4
        
        for i, player in enumerate(self.players):
            if i == discarder_index: continue

            # *** 核心修改：在这里加入“点炮胡”的判断 ***
            # 优先级最高
            if player.can_hu(discarded_tile, self.game_rules):
                possible_actions.append({'type': 'hu', 'player_index': i, 'priority': 3})

            if player.can_kong(discarded_tile):
                possible_actions.append({'type': 'kong', 'player_index': i, 'priority': 2})
            if player.can_pong(discarded_tile):
                possible_actions.append({'type': 'pong', 'player_index': i, 'priority': 2})
            if i == next_player_index:
                chows = player.can_chow(discarded_tile)
                if chows:
                    for chow_pair in chows:
                        possible_actions.append({'type': 'chow', 'player_index': i, 'priority': 1, 'chow_pair': chow_pair})
        
        if not possible_actions:
            return False

        possible_actions.sort(key=lambda x: x['priority'], reverse=True)
        
        # 只处理最高优先级的操作
        highest_priority = possible_actions[0]['priority']
        top_actions = [a for a in possible_actions if a['priority'] == highest_priority]
        
        print("\n--- 操作提示 ---")
        action_map = {}
        for idx, action in enumerate(top_actions):
            # ... (此部分UI逻辑不变) ...
            player = self.players[action['player_index']]; action_type = action['type']
            action_key = f"{idx + 1}"; action_map[action_key] = action
            if action_type == 'chow':
                chow_str = ' '.join(self._replacements.get(t,t) for t in action['chow_pair'])
                print(f"{action_key}: {player.name} 可以 吃 ({chow_str})")
            else:
                print(f"{action_key}: {player.name} 可以 {action_type.capitalize()}!")

        choice = input("有玩家可以操作，请输入序号执行操作，或按 Enter 跳过: ")
        if choice in action_map:
            chosen_action = action_map[choice]
            actor = self.players[chosen_action['player_index']]
            action_type = chosen_action['type']

            # *** 核心修改：处理胡牌 ***
            if action_type == 'hu':
                print(f"🎉🎉🎉 {actor.name} 胡牌！赢家是 {actor.name}！ 🎉🎉🎉")
                print(f"明牌: {' '.join(''.join(self._replacements.get(t,t) for t in meld) for meld in actor.locked_tiles)}")
                print(f"手牌: {' '.join(self._replacements.get(t, t) for t in actor.tiles)}")

                self.game_over = True
                return True # 表示有人行动且游戏结束

            # ... (其他动作处理不变) ...
            elif action_type == 'pong': actor.perform_pong(discarded_tile)
            elif action_type == 'kong':
                actor.perform_kong(discarded_tile)
                # 杠牌后，立刻为该玩家从牌墙补一张牌
                print(f"{actor.name} 从牌墙补张...")
                self.draw_tile(actor)
            elif action_type == 'chow': actor.perform_chow(discarded_tile, chosen_action['chow_pair'])
            
            self.current_player_index = chosen_action['player_index']
            return True

        print("玩家选择跳过。")
        return False

    def start_game(self):
        """
        [重构] 游戏启动入口，设定规则并开始游戏。
        """
        self.game_rules = {
            'rules_name': '福州麻将 (Fuzhou Mahjong)',
            'players_number': 4,
            'tiles_per_player': 16,
            'has_joker': True,
            'joker_count': 4,
            'three_jokers_win': True,
            'allow_all_pairs': False,
            'items_to_remove': {'back', 'spring', 'summer', 'autumn', 'winter', 'plum', 'orchid', 'bamboo', 'chrysanthemum'}
        }
        print(f"--- 载入规则: {self.game_rules['rules_name']} ---")

        self._apply_rules_and_setup_wall()
        
        player_names = ["张三", "李四", "王五", "赵六"]
        for i in range(4):
            player = mahjong_players(i, player_names[i], self.tile_definitions)
            self.players.append(player)
        self.deal_tiles()
        
        banker = self.players[self.current_player_index]
        print(f"\n--- 游戏开始，庄家是 {banker.name} ---")
        self.game_loop()

    def game_loop(self):
        """
        [已整合胡牌判断] 游戏主循环。
        """
        player_just_claimed = False

        while not self.game_over:
            current_player = self.players[self.current_player_index]

            if not player_just_claimed:
                if self.draw_tile(current_player) is None: break
                print(f"牌墙剩余: {len(self.wall)} 张")
                print(f"{current_player.name} 摸到了: {self._replacements.get(current_player.new_tile)}")
                
                # *** 核心修改：在这里加入“自摸”判断 ***
                if current_player.can_hu(None, self.game_rules):
                    choice = current_player.get_player_input(self._replacements, can_zimo=True)
                    if choice == 'hu':
                        print(f"🎉🎉🎉 {current_player.name} 自摸胡牌！ 🎉🎉🎉")
                        self.game_over = True
                        break # 游戏结束，跳出主循环
                    # 如果玩家可以自摸但选择不胡，则正常出牌
                    discarded_tile = current_player.discard_tile(choice)
                else:
                    # 不能自摸，正常出牌
                    choice_idx = current_player.get_player_input(self._replacements)
                    discarded_tile = current_player.discard_tile(choice_idx)
            else:
                # 吃碰杠之后，不需要摸牌，直接出牌
                player_just_claimed = False
                print(f"\n轮到 {current_player.name} 出牌。")
                choice_idx = current_player.get_player_input(self._replacements)
                discarded_tile = current_player.discard_tile(choice_idx)
            
            print(f"{current_player.name} 打出了: {self._replacements.get(discarded_tile, discarded_tile)}")
            self.discarded_pile.append(discarded_tile)
            
            action_taken = self.check_for_claims_and_act(discarded_tile, self.current_player_index)

            if action_taken:
                if self.game_over: break # 如果有人点炮胡，游戏结束
                player_just_claimed = True
            else:
                self.current_player_index = (self.current_player_index + 1) % 4
        
        if not self.game_over:
             print("-" * 40 + "\n牌墙已摸完，流局！\n" + "-" * 40)

# --- 测试 ---
game = mahjong_game()
game.start_game()
# player = mahjong_players(0, "测试玩家", game.tile_definitions)
# player.tiles = ['7t','9t','joker','1w']
# player.sort_tiles()
# print(player.can_hu('1w', game.game_rules))  # 测试胡牌判断


