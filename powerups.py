import pygame
from pygame.math import Vector2
import random

class Powerup: 
    #Base class for all power-ups
    def __init__(self, pos, effect_duration=300):
        """pos: (x, y) position for the powerup to spawn
        effect_duration: how long the effect lasts (frames or milliseconds)"""
        self.rect = pygame.Rect(pos[0], pos[1], 40, 40)
        self.active = True
        self.effect_duration = effect_duration  # Only used for timed effects

    def apply(self, tank):
        #place holder function for subclasses to have their own action upon the tank
        pass

    def update(self):
        #place holder for subclasses' image to animate
        pass

    def draw(self, surf):
        #placeholder for subclasses to draw the power-up
        pygame.draw.rect(surf, (200, 200, 50), self.rect)

class HeartPowerup(Powerup):
    #This powerup gives the player an extra life/added HP

    def draw(self, surf):
        pygame.draw.rect(surf, (255, 50, 50), self.rect)  # Red box for heart

    def apply(self, tank):
        tank.hp += 1  # Add extra life

class HomingBulletPowerup(Powerup):
    #This powerup will allow a player's bullets to follow (hom) the other player for a limited time

    def draw(self, surf):
        pygame.draw.rect(surf, (100, 255, 255), self.rect)  # Cyan

    def apply(self, tank):
        tank.homing_bullet_timer = self.effect_duration
        # You should handle in your Tank code: if homing_bullet_timer > 0, new bullets follow enemy

class DoubleShotPowerup(Powerup):
    #This powerup enables double bullets for the player temporarily

    def draw(self, surf):
        pygame.draw.rect(surf, (0, 255, 100), self.rect)  # Green

    def apply(self, tank):
        tank.double_shot_timer = self.effect_duration
        # In your Tank _shoot() method, check if double_shot_timer > 0 and shoot two bullets

class ShieldPowerup(Powerup):
    #This powerup makes the player invincible for a while with the bubble shield

    def draw(self, surf):
        pygame.draw.rect(surf, (150, 150, 255), self.rect)  # Light blue

    def apply(self, tank):
        tank.shield_timer = self.effect_duration
        # In your Tank code, if shield_timer > 0, ignore incoming damage


def random_powerup(pos):
    #Spawns a random one of the powerups at a random time
    powerup_classes = [HeartPowerup, HomingBulletPowerup, DoubleShotPowerup, ShieldPowerup]
    return random.choice(powerup_classes)(pos)