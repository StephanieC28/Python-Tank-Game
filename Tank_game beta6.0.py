import math
import sys
from typing import List, Tuple
import pygame
from pygame import Rect, Surface
from pygame.math import Vector2
import csv
import os
from powerups import Powerup, HeartPowerup, HomingBulletPowerup, DoubleShotPowerup, ShieldPowerup, random_powerup
import random

def save_score_to_csv(self):
    filename = "player_scores_1.0.csv"
    file_exists = os.path.isfile(filename)

    # Load existing scores
    scores = {}
    if file_exists:
        with open(filename, mode="r", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                scores[row["Player"]] = {
                    "Rank Points": int(row["Rank Points"]),
                    "Net Score": int(row["Net Score"])
                }

    winner = self.winner.name
    loser = self.get_other_tank(self.winner).name
    remaining_hp = self.winner.hp

    for name in [winner, loser]:
        if name not in scores:
            scores[name] = {"Rank Points": 0, "Net Score": 0}

    scores[winner]["Rank Points"] += 3
    scores[winner]["Net Score"] += remaining_hp

    with open(filename, mode="w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["Player", "Rank Points", "Net Score"])
        writer.writeheader()
        for name, data in scores.items():
            writer.writerow({"Player": name, "Rank Points": data["Rank Points"], "Net Score": data["Net Score"]})


class Settings:
    WIDTH, HEIGHT = 1200, 900
    FPS = 60
    BG_COLOR = (255, 255, 255)
    OBSTACLE_COLOR = (100, 100, 100)
    BLACK = (0, 0, 0)
    HEALTH_COLOR = (220, 20, 60)

    TANK_WIDTH = 60
    TANK_HEIGHT = 75
    TANK_SPEED = 15
    TANK_HP = 10

    BULLET_SIZE = 12
    BULLET_SPEED = 15
    BULLET_COOLDOWN = 20
    HIT_COOLDOWN = 30

    FONT_NAME = None
    FONT_SIZE = 48


def load_font(size: int) -> pygame.font.Font:
    if not hasattr(load_font, "cache"):
        load_font.cache = {}
    if size not in load_font.cache:
        pygame.font.init()  # Ensure the font module is initialized
        load_font.cache[size] = pygame.font.SysFont(Settings.FONT_NAME, size)
    return load_font.cache[size]


class Collider:
    def __init__(self, rect: Rect):
        super().__init__()
        self.rect = rect

    def intersects(self, other: Rect) -> bool:
        return self.rect.colliderect(other)


class Obstacle(Collider):
    def __init__(self, x: int, y: int, w: int, h: int):
        super().__init__(Rect(x, y, w, h))

    def draw(self, surf: Surface):
        pygame.draw.rect(surf, Settings.OBSTACLE_COLOR, self.rect)


class Bullet(Collider):
    def __init__(self, pos: Vector2, direction: Vector2, color: Tuple[int, int, int], target=None):
        self.color = color
        self.vel = direction * Settings.BULLET_SPEED
        self.target = target
        super().__init__(Rect(pos.x, pos.y, Settings.BULLET_SIZE, Settings.BULLET_SIZE))

    def update(self):
        if self.target:
            dir_to_target = Vector2(self.target.rect.center) - Vector2(self.rect.center)
            if dir_to_target.length_squared() > 0:
                dir_to_target = dir_to_target.normalize()
                self.vel = dir_to_target * Settings.BULLET_SPEED
        self.rect.x += self.vel.x
        self.rect.y += self.vel.y

    def draw(self, surf: Surface):
        pygame.draw.rect(surf, self.color, self.rect)

    def is_off_screen(self) -> bool:
        r = self.rect
        return r.right < 0 or r.left > Settings.WIDTH or r.bottom < 0 or r.top > Settings.HEIGHT


class Tank(Collider):
    tank_images = {}

    def __init__(self, pos: Vector2, color: Tuple[int, int, int], controls: dict, name: str, player_index: int):
        self.name = name
        self.color = color
        self.controls = controls
        self.hp = Settings.TANK_HP
        self.score = 0
        self.angle = 0
        self.bullets = []
        self._reload_timer = 0
        self._hit_timer = 0
        self.outside_safezone_cooldown = 0
        self.is_draw = False
        if player_index not in Tank.tank_images:
            if player_index == 0:
                image_path = "Player1_tank.png"
            else:
                image_path = "Player2_tank.png"

            try:
                Tank.tank_images[player_index] = pygame.image.load(image_path).convert_alpha()
            except pygame.error:
                surf = pygame.Surface((Settings.TANK_WIDTH, Settings.TANK_HEIGHT))
                surf.fill(self.color)
                Tank.tank_images[player_index] = surf

        self.original_image = pygame.transform.scale(
            Tank.tank_images[player_index], (Settings.TANK_WIDTH, Settings.TANK_HEIGHT)
        )
        self.image = self.original_image
        rect = self.original_image.get_rect(center=pos)
        super().__init__(rect)

    def handle_input(self, keys):
        movement = Vector2(0, 0)
        if keys[self.controls['left']]:
            movement.x -= 1
        if keys[self.controls['right']]:
            movement.x += 1
        if keys[self.controls['up']]:
            movement.y -= 1
        if keys[self.controls['down']]:
            movement.y += 1
        if movement.length_squared() > 0:
            movement = movement.normalize()
            new_pos = Vector2(self.rect.center) + movement * Settings.TANK_SPEED
            new_rect = self.rect.copy()
            new_rect.center = new_pos
            self.angle = math.degrees(math.atan2(-movement.y, movement.x)) % 360
            if not (0 <= new_rect.left and new_rect.right <= Settings.WIDTH and
                    0 <= new_rect.top and new_rect.bottom <= Settings.HEIGHT):
                return
            if not Game.instance().cheat_wall:
                for collider in Game.instance().colliders:
                    if collider is not self and new_rect.colliderect(collider.rect):
                        return
            self.rect.center = new_pos
        if keys[self.controls['shoot']] and self._reload_timer == 0:
            self._shoot()

    def _shoot(self):
        rad = math.radians(self.angle)
        offset = Vector2(math.cos(rad), -math.sin(rad)) * 40
        pos = Vector2(self.rect.center) + offset
        vel = Vector2(math.cos(rad), -math.sin(rad))
        target = None

        game = Game.instance()
        if game and (game.cheat_tank_name == self.name or game.cheat_tank_name == "Both"):
            target = game.get_other_tank(self)

        self.bullets.append(Bullet(pos, vel, self.color, target))

        if game and game.bullet_hack:
            for angle_offset in [-130, -75, 75, 130]:
                offset_rad = math.radians(self.angle + angle_offset)
                offset_vel = Vector2(math.cos(offset_rad), -math.sin(offset_rad))
                self.bullets.append(Bullet(pos, offset_vel, self.color, target))

        if hasattr(self, "double_shot_timer") and self.double_shot_timer > 0:
            # Shoot two bullets
            for offset_angle in [-10, 10]:
                rad = math.radians(self.angle + offset_angle)
                offset = Vector2(math.cos(rad), -math.sin(rad)) * 40
                pos = Vector2(self.rect.center) + offset
                vel = Vector2(math.cos(rad), -math.sin(rad))
                target = None
                if hasattr(self, "homing_bullet_timer") and self.homing_bullet_timer > 0:
                    target = Game.instance().get_other_tank(self)
                self.bullets.append(Bullet(pos, vel, self.color, target))
        else:
            # Normal single bullet
            rad = math.radians(self.angle)
            offset = Vector2(math.cos(rad), -math.sin(rad)) * 40
            pos = Vector2(self.rect.center) + offset
            vel = Vector2(math.cos(rad), -math.sin(rad))
            target = None
            if hasattr(self, "homing_bullet_timer") and self.homing_bullet_timer > 0:
                target = Game.instance().get_other_tank(self)
            self.bullets.append(Bullet(pos, vel, self.color, target))

        self._reload_timer = Settings.BULLET_COOLDOWN

    def update(self):
        if self.outside_safezone_cooldown > 0:
            self.outside_safezone_cooldown -= 1
        if self._reload_timer > 0:
            self._reload_timer -= 1
        if self._hit_timer > 0:
            self._hit_timer -= 1

        for b in self.bullets[:]:
            b.update()
            if b.is_off_screen() or Game.instance().check_bullet_obstacle(b):
                self.bullets.remove(b)
            elif Game.instance().check_bullet_tank(b, self):
                self.bullets.remove(b)
                victim = Game.instance().get_other_tank(self)
                # ✅ Shield protection logic
                if not hasattr(victim, "shield_timer") or victim.shield_timer <= 0:
                    victim.hp -= 1

        # ✅ Timed powerup effects
        if hasattr(self, "homing_bullet_timer") and self.homing_bullet_timer > 0:
            self.homing_bullet_timer -= 1
        if hasattr(self, "double_shot_timer") and self.double_shot_timer > 0:
            self.double_shot_timer -= 1
        if hasattr(self, "shield_timer") and self.shield_timer > 0:
            self.shield_timer -= 1

    def draw(self, surf: Surface):
        # Rotate the tank image based on angle
        rotated_image = pygame.transform.rotate(self.original_image, self.angle)
        rotated_rect = rotated_image.get_rect(center=self.rect.center)
        surf.blit(rotated_image, rotated_rect)

        # Draw shield circle if shield is active
        if hasattr(self, "shield_timer") and self.shield_timer > 0:
            pygame.draw.circle(
                surf,
                (135, 206, 250),  # Light blue color
                self.rect.center,
                max(self.rect.width, self.rect.height) // 2 + 15,
                4  # Thickness of the ring
            )

        # Draw health blocks
        for i in range(self.hp):
            x = self.rect.left + i * 22
            y = self.rect.top - 25
            pygame.draw.rect(surf, Settings.HEALTH_COLOR, (x, y, 20, 20))


class Game:
    _inst = None

    @classmethod
    def instance(cls):
        return cls._inst

    def save_score_to_csv(self):
        filename = "player_scores.csv"
        file_exists = os.path.isfile(filename)

        scores = {}
        if file_exists:
            with open(filename, mode="r", newline="") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    scores[row["Player"]] = {
                        "Rank Points": int(row["Rank Points"]),
                        "Net Score": int(row["Net Score"])
                    }

        player1_name, player2_name = self.player_names
        player1_score = self.tanks[0].score
        player2_score = self.tanks[1].score

        for name in [player1_name, player2_name]:
            if name not in scores:
                scores[name] = {"Rank Points": 0, "Net Score": 0}

        if self.is_draw:
            scores[player1_name]["Rank Points"] += 5
            scores[player2_name]["Rank Points"] += 5
        else:
            if self.winner == self.tanks[0]:
                winner_name = player1_name
                remaining_hp = self.tanks[0].hp
            else:
                winner_name = player2_name
                remaining_hp = self.tanks[1].hp

            scores[winner_name]["Rank Points"] += 10
            scores[winner_name]["Net Score"] += remaining_hp

        with open(filename, mode="w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=["Player", "Rank Points", "Net Score"])
            writer.writeheader()
            for name, data in scores.items():
                writer.writerow({"Player": name, "Rank Points": data["Rank Points"], "Net Score": data["Net Score"]})

    def __init__(self):
        Game._inst = self
        pygame.init()
        self.screen = pygame.display.set_mode((Settings.WIDTH, Settings.HEIGHT))
        pygame.display.set_caption("Super Tank")
        self.clock = pygame.time.Clock()
        self.running = True
        self.in_menu = True
        self.difficulty = 0
        self.cheat_tank_name = None
        self.cheat_wall = False
        self.bullet_hack = False
        self.bullet_through_wall = False
        self.safe_zone_center = Vector2(Settings.WIDTH // 2, Settings.HEIGHT // 2)
        self.safe_zone_radius = math.hypot(Settings.WIDTH, Settings.HEIGHT) / 2
        self.shrink_timer = 0
        self.shrink_interval = 30 * Settings.FPS
        self.shrinking = False
        self.safe_zone_visible = False
        self.player_names = ["Player1", "Player2"]
        self.is_restarting = False
        self.winner = None
        # --- Added for player input UI ---
        self.player_input_active = False
        self.input_boxes = [pygame.Rect(Settings.WIDTH // 2 - 250, 250, 400, 40),
                            pygame.Rect(Settings.WIDTH // 2 - 250, 320, 400, 40)]
        self.player_inputs = ["", ""]
        self.confirmed = [False, False]
        self.input_font = load_font(32)
        self.powerups = []
        self.bullet_hack = False
        self.is_draw = False
        self.powerups = []
        self.powerup_spawn_timer = 0
        self.powerup_spawn_interval = 5 * Settings.FPS  # Spawn every 5 seconds
        self.restart()

    def quit_game(self):
        pygame.quit()
        sys.exit()

    def select_difficulty(self):
        font = load_font(36)
        small_font = load_font(24)
        button_width, button_height = 200, 60
        gap = 80
        total_height = 3 * button_height + 2 * gap
        start_y = (Settings.HEIGHT - total_height) // 2
        center_x = (Settings.WIDTH - button_width) // 2

        buttons = [
            ("Easy", pygame.Rect(center_x, start_y, button_width, button_height)),
            ("Medium", pygame.Rect(center_x, start_y + button_height + gap, button_width, button_height)),
            ("Hard", pygame.Rect(center_x, start_y + 2 * (button_height + gap), button_width, button_height)),
        ]

        while True:
            self.screen.fill((180, 180, 180))
            for text, rect in buttons:
                pygame.draw.rect(self.screen, (100, 100, 100), rect)
                label = font.render(text, True, (255, 255, 255))
                label_rect = label.get_rect(center=rect.center)
                self.screen.blit(label, label_rect)

            hint_text = small_font.render("Press ESC to return to menu", True, (50, 50, 50))
            hint_rect = hint_text.get_rect(center=(Settings.WIDTH // 2, Settings.HEIGHT - 50))
            self.screen.blit(hint_text, hint_rect)

            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.quit_game()
                if e.type == pygame.MOUSEBUTTONDOWN:
                    for idx, (_, rect) in enumerate(buttons):
                        if rect.collidepoint(e.pos):
                            self.difficulty = idx
                            return
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE:
                        return

            pygame.display.flip()

    def restart(self):
        self.safe_zone_radius = math.hypot(Settings.WIDTH, Settings.HEIGHT) / 2
        self.shrink_timer = 0
        self.shrinking = False
        self.safe_zone_visible = False
        self.winner = None

        if self.difficulty == 0:
            self.obstacles = [Obstacle(460, 235, 60, 280)]
        elif self.difficulty == 1:
            self.obstacles = [
                Obstacle(310, 160, 60, 430),
                Obstacle(825, 150, 75, 450),
                Obstacle(562, 0, 75, 225),
                Obstacle(562, 675, 75, 225),
            ]
        else:
            self.obstacles = [
                Obstacle(225, 120, 75, 300),
                Obstacle(300, 525, 75, 300),
                Obstacle(900, 120, 75, 300),
                Obstacle(750, 525, 75, 300),
                Obstacle(450, 225, 300, 30),
                Obstacle(460, 650, 280, 20),
                Obstacle(562, 30, 75, 150),
                Obstacle(562, 720, 75, 150),
                Obstacle(75, 412, 225, 75),
                Obstacle(900, 412, 225, 75),
                Obstacle(562, 412, 75, 75)
            ]

        if self.difficulty != 2:
            self.tanks = [
                Tank(Vector2(100, Settings.HEIGHT // 2), (0, 0, 255),
                     dict(up=pygame.K_w, down=pygame.K_s, left=pygame.K_a, right=pygame.K_d, shoot=pygame.K_SPACE),
                     self.player_names[0], player_index=0),
                Tank(Vector2(Settings.WIDTH - 100, Settings.HEIGHT // 2), (0, 255, 0),
                     dict(up=pygame.K_UP, down=pygame.K_DOWN, left=pygame.K_LEFT, right=pygame.K_RIGHT,
                          shoot=pygame.K_RETURN),
                     self.player_names[1], player_index=1),
            ]
        else:
            blue_spawn = Vector2(75, 100)
            green_spawn = Vector2(Settings.WIDTH - 75, Settings.HEIGHT - 100)
            self.tanks = [
                Tank(blue_spawn, (0, 0, 255),
                     dict(up=pygame.K_w, down=pygame.K_s, left=pygame.K_a, right=pygame.K_d, shoot=pygame.K_SPACE),
                     self.player_names[0], player_index=0),
                Tank(green_spawn, (0, 255, 0),
                     dict(up=pygame.K_UP, down=pygame.K_DOWN, left=pygame.K_LEFT, right=pygame.K_RIGHT,
                          shoot=pygame.K_RETURN),
                     self.player_names[1], player_index=1),
            ]

    @property
    def colliders(self):
        return self.obstacles + self.tanks

    def check_bullet_obstacle(self, bullet: Bullet) -> bool:
        return any(bullet.intersects(ob.rect) for ob in self.obstacles)

    def check_bullet_tank(self, bullet: Bullet, owner: Tank) -> bool:
        for t in self.tanks:
            if t is not owner and bullet.intersects(t.rect):
                return True
        return False

    def get_other_tank(self, tank: Tank) -> Tank:
        return self.tanks[0] if tank is self.tanks[1] else self.tanks[1]

    def show_menu(self):
        font = load_font(48)
        small_font = load_font(36)
        version_font = load_font(24)
        start_button = pygame.Rect(Settings.WIDTH // 2 - 100, 200, 200, 60)
        setting_button = pygame.Rect(Settings.WIDTH // 2 - 100, 280, 200, 60)
        difficulty_button = pygame.Rect(Settings.WIDTH // 2 - 100, 360, 200, 60)
        instruction_button = pygame.Rect(Settings.WIDTH // 2 - 100, 440, 200, 60)
        ranking_button = pygame.Rect(Settings.WIDTH // 2 - 100, 520, 200, 60)

        while True:
            self.screen.fill((240, 240, 240))
            title = font.render("Tank Game", True, (0, 0, 0))
            self.screen.blit(title, title.get_rect(center=(Settings.WIDTH // 2, 100)))

            pygame.draw.rect(self.screen, (0, 200, 0), start_button)
            pygame.draw.rect(self.screen, (0, 0, 200), setting_button)
            pygame.draw.rect(self.screen, (200, 0, 0), difficulty_button)
            pygame.draw.rect(self.screen, (100, 100, 100), instruction_button)
            pygame.draw.rect(self.screen, (255, 140, 0), ranking_button)

            self.screen.blit(small_font.render("START", True, (255, 255, 255)),
                             (start_button.x + 50, start_button.y + 10))
            self.screen.blit(small_font.render("SETTING", True, (255, 255, 255)),
                             (setting_button.x + 30, setting_button.y + 10))
            self.screen.blit(small_font.render("DIFFICULTY", True, (255, 255, 255)),
                             (difficulty_button.x + 20, difficulty_button.y + 10))
            self.screen.blit(small_font.render("INSTRUCTION", True, (255, 255, 255)),
                             (instruction_button.x + 15, instruction_button.y + 10))
            self.screen.blit(small_font.render("RANKING", True, (255, 255, 255)),
                             (ranking_button.x + 30, ranking_button.y + 10))

            version_text = version_font.render("Beta Version 5.6", True, (150, 150, 150))
            version_rect = version_text.get_rect(bottomright=(Settings.WIDTH - 10, Settings.HEIGHT - 10))
            self.screen.blit(version_text, version_rect)

            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.quit_game()
                if e.type == pygame.MOUSEBUTTONDOWN:
                    if start_button.collidepoint(e.pos):
                        self.show_account_input()
                        return
                    if setting_button.collidepoint(e.pos):
                        self.show_settings()
                    if difficulty_button.collidepoint(e.pos):
                        self.select_difficulty()
                    if instruction_button.collidepoint(e.pos):
                        self.show_instruction()
                    if ranking_button.collidepoint(e.pos):
                        self.show_ranking()

            pygame.display.flip()

    def show_ranking(self):
        font = load_font(36)
        title_font = load_font(48)
        hint_font = load_font(24)
        bg_color = (200, 200, 200)
        text_color = (0, 0, 0)

        try:
            with open("player_scores.csv", newline='') as csvfile:
                reader = csv.reader(csvfile)
                next(reader, None)
                ranking_list = [row for row in reader if len(row) >= 2 and row[1].isdigit()]
                ranking_list = sorted(ranking_list, key=lambda row: int(row[1]), reverse=True)
        except FileNotFoundError:
            ranking_list = []

        while True:
            self.screen.fill(bg_color)
            title = title_font.render("Ranking", True, (50, 50, 50))
            self.screen.blit(title, title.get_rect(center=(Settings.WIDTH // 2, 80)))

            for idx, row in enumerate(ranking_list):
                name, score = row[0], row[1]
                text = f"{idx + 1}. {name} - {score} pts"
                rendered = font.render(text, True, text_color)
                self.screen.blit(rendered, (Settings.WIDTH // 2 - 200, 150 + idx * 50))

            hint_text = hint_font.render("Press ESC to return to menu", True, (0, 0, 0))
            hint_rect = hint_text.get_rect(center=(Settings.WIDTH // 2, Settings.HEIGHT - 40))
            self.screen.blit(hint_text, hint_rect)

            back_font = load_font(28)
            back_text = back_font.render("Back to Menu", True, (0, 0, 0))
            back_rect = back_text.get_rect(center=(Settings.WIDTH // 2, Settings.HEIGHT - 80))
            pygame.draw.rect(self.screen, (180, 180, 180), back_rect.inflate(20, 10))
            self.screen.blit(back_text, back_rect)

            pygame.display.flip()

            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.quit_game()
                if e.type == pygame.MOUSEBUTTONDOWN:
                    if back_rect.collidepoint(e.pos):
                        return
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE:
                        return

    def show_instruction(self):
        font = load_font(28)
        lines = [
            "Instructions:",
            "",
            "Player 1 (Blue):",
            "  Move: W A S D",
            "  Shoot: Space",
            "",
            "Player 2 (Green):",
            "  Move: Arrow Keys",
            "  Shoot: Enter",
            "Stay within the safe bubble or loose health",
            "",
            "Collect the power up squares to gain more power",
            "The four Power-ups are:",
            "1. Extra Heart: Red",
            "2. Homing Bullets: Yellow",
            "3. Extra Bullets: Green",
            "4. Sheild: Blue",
            "",
            "Press ESC to return to menu."
        ]

        while True:
            self.screen.fill((200, 200, 200))
            total_height = len(lines) * 40
            start_y = (Settings.HEIGHT - total_height) // 2

            for i, line in enumerate(lines):
                text_surf = font.render(line, True, (0, 0, 0))
                text_rect = text_surf.get_rect(center=(Settings.WIDTH // 2, start_y + i * 40))
                self.screen.blit(text_surf, text_rect)

            pygame.display.flip()

            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE:
                        return

    def show_settings(self):
        font = load_font(32)
        sliders = {
            "Speed": [Settings.TANK_SPEED, 1, 20],
            "Size": [Settings.TANK_WIDTH, 20, 200],
            "FireRate": [Settings.BULLET_COOLDOWN, 1, 100],
            "HP": [Settings.TANK_HP, 1, 100]
        }
        slider_rects = {}
        start_y = 200
        gap = 80
        slider_width = 400
        center_x = Settings.WIDTH // 2 - slider_width // 2

        for idx, key in enumerate(sliders):
            slider_rects[key] = pygame.Rect(center_x, start_y + idx * gap, slider_width, 20)

        cheat_button = pygame.Rect(Settings.WIDTH // 2 - 100, start_y + len(sliders) * gap + 50, 200, 40)

        while True:
            self.screen.fill((220, 220, 220))

            for idx, (key, (val, min_val, max_val)) in enumerate(sliders.items()):
                label = font.render(f"{key}: {int(val)}", True, (0, 0, 0))
                label_rect = label.get_rect(center=(Settings.WIDTH // 2, start_y + idx * gap - 30))
                self.screen.blit(label, label_rect)
                pygame.draw.rect(self.screen, (170, 170, 170), slider_rects[key])
                knob_x = slider_rects[key].x + int((val - min_val) / (max_val - min_val) * slider_rects[key].width)
                pygame.draw.circle(self.screen, (40, 40, 40), (knob_x, slider_rects[key].centery), 10)

            pygame.draw.rect(self.screen, (200, 0, 200), cheat_button)
            cheat_label = font.render("Cheat", True, (255, 255, 255))
            cheat_label_rect = cheat_label.get_rect(center=cheat_button.center)
            self.screen.blit(cheat_label, cheat_label_rect)

            hint_font = load_font(24)
            hint_text = hint_font.render("ESC: Menu    ENTER: Confirm", True, (50, 50, 50))
            hint_rect = hint_text.get_rect(center=(Settings.WIDTH // 2, Settings.HEIGHT - 50))
            self.screen.blit(hint_text, hint_rect)

            pygame.display.flip()

            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if e.type == pygame.MOUSEBUTTONDOWN:
                    if cheat_button.collidepoint(e.pos):
                        self.show_cheat_menu()
                        continue
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE:
                        self.show_menu()
                        return
                    if e.key == pygame.K_RETURN:
                        Settings.TANK_SPEED = sliders["Speed"][0]
                        Settings.TANK_WIDTH = sliders["Size"][0]
                        Settings.TANK_HEIGHT = sliders["Size"][0] + 10
                        Settings.BULLET_COOLDOWN = int(sliders["FireRate"][0])
                        Settings.TANK_HP = int(sliders["HP"][0])
                        return
                if e.type == pygame.MOUSEMOTION and e.buttons[0]:
                    for key, rect in slider_rects.items():
                        if rect.collidepoint(e.pos):
                            min_val, max_val = sliders[key][1], sliders[key][2]
                            rel_x = e.pos[0] - rect.x
                            rel_x = max(0, min(rel_x, rect.width))
                            sliders[key][0] = min_val + (rel_x / rect.width) * (max_val - min_val)

    def show_cheat_menu(self):
        font = load_font(36)
        button_width, button_height = 200, 60
        start_y = 120
        line_height = 70
        center_x = Settings.WIDTH // 2 - button_width // 2

        blue_button = pygame.Rect(center_x, start_y, button_width, button_height)
        green_button = pygame.Rect(center_x, start_y + line_height, button_width, button_height)
        both_button = pygame.Rect(center_x, start_y + line_height * 2, button_width, button_height)
        wall_button = pygame.Rect(center_x, start_y + line_height * 3, button_width, button_height)
        bullet_button = pygame.Rect(center_x, start_y + line_height * 4, button_width, button_height)
        through_wall_button = pygame.Rect(center_x, start_y + line_height * 5, button_width, button_height)
        quit_button = pygame.Rect(center_x, start_y + line_height * 6, button_width, button_height)

        while True:
            self.screen.fill((150, 150, 150))
            pygame.draw.rect(self.screen, (0, 0, 255), blue_button)
            pygame.draw.rect(self.screen, (0, 255, 0), green_button)
            pygame.draw.rect(self.screen, (128, 0, 128), both_button)
            pygame.draw.rect(self.screen, (255, 165, 0), wall_button)
            pygame.draw.rect(self.screen, (255, 0, 0), bullet_button)
            pygame.draw.rect(self.screen, (0, 128, 255), through_wall_button)
            pygame.draw.rect(self.screen, (150, 0, 0), quit_button)

            self.screen.blit(font.render("Blue Cheat", True, (255, 255, 255)), (blue_button.x + 30, blue_button.y + 10))
            self.screen.blit(font.render("Green Cheat", True, (255, 255, 255)),
                             (green_button.x + 20, green_button.y + 10))
            self.screen.blit(font.render("Both Cheat", True, (255, 255, 255)), (both_button.x + 30, both_button.y + 10))
            self.screen.blit(font.render("Wall Hack", True, (255, 255, 255)), (wall_button.x + 30, wall_button.y + 10))
            self.screen.blit(font.render("5 Bullet a time", True, (255, 255, 255)),
                             (bullet_button.x + 30, bullet_button.y + 10))
            self.screen.blit(font.render("Through Wall", True, (255, 255, 255)),
                             (through_wall_button.x + 10, through_wall_button.y + 10))
            self.screen.blit(font.render("Cancel All", True, (255, 255, 255)), (quit_button.x + 30, quit_button.y + 10))

            pygame.display.flip()
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if e.type == pygame.MOUSEBUTTONDOWN:
                    if blue_button.collidepoint(e.pos):
                        self.cheat_tank_name = "Blue"
                        return
                    if green_button.collidepoint(e.pos):
                        self.cheat_tank_name = "Green"
                        return
                    if both_button.collidepoint(e.pos):
                        self.cheat_tank_name = "Both"
                        return
                    if wall_button.collidepoint(e.pos):
                        self.cheat_wall = True
                        return
                    if bullet_button.collidepoint(e.pos):
                        self.bullet_hack = True
                        return
                    if through_wall_button.collidepoint(e.pos):
                        self.bullet_through_wall = True
                        return
                    if quit_button.collidepoint(e.pos):
                        self.cheat_tank_name = None
                        self.cheat_wall = False
                        self.bullet_hack = False
                        self.bullet_through_wall = False
                        return

    def show_account_input(self):
        self.player_input_active = True
        active_box = [False, False]

        input_width, input_height = 300, 40
        gap = 80
        start_y = (Settings.HEIGHT - (2 * input_height + gap)) // 2
        center_x = Settings.WIDTH // 2 - input_width // 2

        self.input_boxes = [
            pygame.Rect(center_x, start_y, input_width, input_height),
            pygame.Rect(center_x, start_y + input_height + gap, input_width, input_height)
        ]

        confirm_buttons = [
            pygame.Rect(Settings.WIDTH // 2 + input_width // 2 + 20, start_y, 100, 40),
            pygame.Rect(Settings.WIDTH // 2 + input_width // 2 + 20, start_y + input_height + gap, 100, 40)
        ]

        self.player_inputs = ["", ""]
        self.confirmed = [False, False]

        while not all(self.confirmed):
            self.screen.fill((240, 240, 240))
            label = load_font(40).render("Enter Player Names", True, (0, 0, 0))
            self.screen.blit(label, label.get_rect(center=(Settings.WIDTH // 2, 120)))

            for i in range(2):
                pygame.draw.rect(self.screen, (0, 0, 0), self.input_boxes[i], 2)
                input_surface = self.input_font.render(self.player_inputs[i], True, (0, 0, 0))
                self.screen.blit(input_surface, (self.input_boxes[i].x + 5, self.input_boxes[i].y + 5))

                pygame.draw.rect(self.screen, (0, 200, 0) if not self.confirmed[i] else (100, 100, 100),
                                 confirm_buttons[i])
                confirm_text = self.input_font.render("Confirm", True, (255, 255, 255))
                self.screen.blit(confirm_text, confirm_text.get_rect(center=confirm_buttons[i].center))

            hint_font = load_font(24)
            hint_text = hint_font.render("Press ESC to return to menu", True, (50, 50, 50))
            hint_rect = hint_text.get_rect(center=(Settings.WIDTH // 2, Settings.HEIGHT - 50))
            self.screen.blit(hint_text, hint_rect)

            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.quit_game()
                if event.type == pygame.MOUSEBUTTONDOWN:
                    for i in range(2):
                        if self.input_boxes[i].collidepoint(event.pos):
                            active_box = [j == i for j in range(2)]
                        if confirm_buttons[i].collidepoint(event.pos):
                            if self.player_inputs[i]:
                                self.confirmed[i] = True
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.show_menu()
                        return
                    for i in range(2):
                        if active_box[i] and not self.confirmed[i]:
                            if event.key == pygame.K_BACKSPACE:
                                self.player_inputs[i] = self.player_inputs[i][:-1]
                            elif len(self.player_inputs[i]) < 20 and event.unicode.isprintable():
                                self.player_inputs[i] += event.unicode

        self.player_names = self.player_inputs[:2]
        self.countdown()

    def countdown(self):
        for i in range(3, 0, -1):
            self.screen.fill((240, 240, 240))
            text = load_font(72).render(str(i), True, (0, 0, 0))
            self.screen.blit(text, text.get_rect(center=(Settings.WIDTH // 2, Settings.HEIGHT // 2)))
            pygame.display.flip()
            pygame.time.delay(1000)

    def game_loop(self):
        self.running = True
        self.winner = None
        self.restart()

        while self.running:
            self.clock.tick(Settings.FPS)
            self.handle_events()
            if not self.winner:
                self.update()
            self.draw()

    def handle_events(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self.quit_game()
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    self.running = False
                if self.winner and e.key == pygame.K_r:
                    self.restart()
                    self.winner = None
            elif e.type == pygame.MOUSEBUTTONDOWN:
                if hasattr(self, "back_rect") and self.back_rect.collidepoint(e.pos):
                    self.running = False

        if not self.winner:
            keys = pygame.key.get_pressed()
            for t in self.tanks:
                t.handle_input(keys)

    def update(self):
        self.shrink_timer += 1
        # Handle powerup spawning
        self.powerup_spawn_timer += 1
        if self.powerup_spawn_timer >= self.powerup_spawn_interval:
            self.spawn_powerup()
            self.powerup_spawn_timer = 0

        if not self.shrinking and self.shrink_timer >= self.shrink_interval:
            self.shrinking = True
            self.safe_zone_visible = True
            self.shrink_timer = 0
        if self.shrinking:
            self.safe_zone_radius = max(50, self.safe_zone_radius - 0.1)

        for t in self.tanks:
            t.update()
            if t.hp <= 0:
                self.winner = self.get_other_tank(t)
                break

        for t in self.tanks:
            distance = Vector2(t.rect.center).distance_to(self.safe_zone_center)
            if distance > self.safe_zone_radius and t.hp > 0:
                if t.outside_safezone_cooldown <= 0:
                    t.hp -= 1
                    t.outside_safezone_cooldown = Settings.FPS

        blue_dead = self.tanks[0].hp <= 0
        green_dead = self.tanks[1].hp <= 0
        if blue_dead and green_dead and not self.winner:
            self.is_draw = True
        elif blue_dead and not self.winner:
            self.winner = self.tanks[1]
        elif green_dead and not self.winner:
            self.winner = self.tanks[0]
        
        for powerup in self.powerups[:]:
            for tank in self.tanks:
                if powerup.active and tank.rect.colliderect(powerup.rect):
                    powerup.apply(tank)
                    powerup.active = False
                    self.powerups.remove(powerup)


    def spawn_powerup(self):
        max_attempts = 50  # Prevent infinite loops & only allowed to find a spawn spot 50 times
        for _ in range(max_attempts):
            x = random.randint(50, Settings.WIDTH - 90)
            y = random.randint(50, Settings.HEIGHT - 90)
            new_rect = pygame.Rect(x, y, 40, 40)

            # Check if it collides with any obstacle, if not, spawn
            if all(not new_rect.colliderect(ob.rect) for ob in self.obstacles):
                new_powerup = random_powerup((x, y))
                self.powerups.append(new_powerup)
                return
        # If no valid spot found after max_attempts, skip spawning


    def draw(self):
        self.screen.fill(Settings.BG_COLOR)
        if self.safe_zone_visible:
            pygame.draw.circle(self.screen, (0, 0, 255), self.safe_zone_center, int(self.safe_zone_radius), 2)

        for ob in self.obstacles:
            ob.draw(self.screen)

        for t in self.tanks:
            t.draw(self.screen)
            for b in t.bullets:
                b.draw(self.screen)

        for powerup in self.powerups:
            powerup.draw(self.screen)

        if (self.winner or self.is_draw) and not self.is_restarting:
            self.save_score_to_csv()
            self.is_restarting = True

        if self.winner or self.is_draw:
            if self.is_draw:
                msg = "Draw!"
                color = (128, 128, 128)
            else:
                msg = f"{self.winner.name} Tank Wins!"
                color = (220, 20, 60)

            font = load_font(Settings.FONT_SIZE)
            text = font.render(msg, True, (255, 255, 255))
            rect = text.get_rect(center=(Settings.WIDTH // 2, Settings.HEIGHT // 2))

            padding = 20
            bg_rect = pygame.Rect(rect.left - padding, rect.top - padding,
                                  rect.width + padding * 2, rect.height + padding * 2)
            pygame.draw.rect(self.screen, color, bg_rect, border_radius=10)
            pygame.draw.rect(self.screen, (0, 0, 0), bg_rect, width=5, border_radius=10)
            self.screen.blit(text, rect)

            restart_text = load_font(32).render("Press R to Restart", True, (200, 200, 200))
            restart_rect = restart_text.get_rect(center=(Settings.WIDTH // 2, Settings.HEIGHT // 2 + 60))
            self.screen.blit(restart_text, restart_rect)

            menu_text = load_font(32).render("Press ESC for Menu", True, (200, 200, 200))
            menu_rect = menu_text.get_rect(center=(Settings.WIDTH // 2, Settings.HEIGHT // 2 + 100))
            self.screen.blit(menu_text, menu_rect)

        font = load_font(24)
        back_text = font.render("Menu", True, (0, 0, 0))
        self.back_rect = back_text.get_rect(topright=(Settings.WIDTH - 20, 20))
        pygame.draw.rect(self.screen, (200, 200, 200), self.back_rect.inflate(10, 10))
        self.screen.blit(back_text, self.back_rect)

        pygame.display.flip()

    def run(self):
        while True:
            self.show_menu()
            self.game_loop()


if __name__ == "__main__":
    Game().run()
