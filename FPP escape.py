import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import math
import random

# Initialize pygame
pygame.init()
pygame.mixer.init()
width, height = 800, 600
pygame.display.set_mode((width, height), DOUBLEBUF | OPENGL)

# Game constants
MOVE_SPEED = 0.15
MOUSE_SENSITIVITY = 0.2
GRAVITY = 0.05
JUMP_FORCE = 0.5
MAX_FPS = 60

# Player class
class Player:
    def __init__(self):
        self.pos = [1.5, 1.0, 1.5]  # x, y, z
        self.rot = [0, 0]  # yaw, pitch
        self.vel = [0, 0, 0]  # x, y, z velocity
        self.on_ground = False
        self.collected_items = 0

    def update_position(self, world):
        # Apply gravity
        self.vel[1] -= GRAVITY

        # Calculate movement
        move_vec = [0, 0, 0]
        yaw_rad = math.radians(self.rot[0])

        keys = pygame.key.get_pressed()
        if keys[K_w]:
            move_vec[0] += math.sin(yaw_rad) * MOVE_SPEED
            move_vec[2] -= math.cos(yaw_rad) * MOVE_SPEED
        if keys[K_s]:
            move_vec[0] -= math.sin(yaw_rad) * MOVE_SPEED
            move_vec[2] += math.cos(yaw_rad) * MOVE_SPEED
        if keys[K_a]:
            move_vec[0] -= math.cos(yaw_rad) * MOVE_SPEED
            move_vec[2] -= math.sin(yaw_rad) * MOVE_SPEED
        if keys[K_d]:
            move_vec[0] += math.cos(yaw_rad) * MOVE_SPEED
            move_vec[2] += math.sin(yaw_rad) * MOVE_SPEED

        # Jumping
        if keys[K_SPACE] and self.on_ground:
            self.vel[1] = JUMP_FORCE
            self.on_ground = False

        # Apply movement
        self.vel[0] = move_vec[0]
        self.vel[2] = move_vec[2]

        # Calculate tentative new position
        new_pos = [self.pos[i] + self.vel[i] for i in range(3)]

        # Collision detection with walls for x and z separately to allow sliding along walls
        def is_blocked(x, y, z):
            map_layers = len(world.map)
            map_depth = len(world.map[0])
            map_width = len(world.map[0][0])
            if y < 0 or y >= map_layers or z < 0 or z >= map_depth or x < 0 or x >= map_width:
                return True  # outside world bounds treated as blocked
            return world.map[int(y)][int(z)][int(x)] != 0

        # Check X movement
        if not is_blocked(new_pos[0], self.pos[1], self.pos[2]):
            self.pos[0] = new_pos[0]
        else:
            self.vel[0] = 0
        # Check Z movement
        if not is_blocked(self.pos[0], self.pos[1], new_pos[2]):
            self.pos[2] = new_pos[2]
        else:
            self.vel[2] = 0
        # Check Y movement (vertical)
        if self.vel[1] != 0:
            if self.vel[1] > 0:  # moving up
                if not is_blocked(self.pos[0], new_pos[1] + 0.9, self.pos[2]):
                    self.pos[1] = new_pos[1]
                else:
                    self.vel[1] = 0
            else:  # moving down
                if not is_blocked(self.pos[0], new_pos[1], self.pos[2]):
                    self.pos[1] = new_pos[1]
                    self.on_ground = False
                else:
                    self.vel[1] = 0
                    self.on_ground = True
                    self.pos[1] = math.floor(self.pos[1]) + 1.0  # place on top of block

    def handle_mouse(self, rel_x, rel_y):
        self.rot[0] += rel_x * MOUSE_SENSITIVITY
        self.rot[1] -= rel_y * MOUSE_SENSITIVITY

        # Clamp pitch
        self.rot[1] = max(-90, min(90, self.rot[1]))

# World class
class World:
    def __init__(self):
        self.map = self.generate_map()
        self.items = self.generate_items()
        self.textures = self.load_textures()

    def generate_map(self):
        map_layers = 3
        map_size = 20

        # Empty map
        world_map = [[[0 for _ in range(map_size)] for _ in range(map_size)] for _ in range(map_layers)]

        # Outer walls
        for y in range(map_layers):
            for z in range(map_size):
                for x in range(map_size):
                    if x == 0 or x == map_size-1 or z == 0 or z == map_size-1:
                        world_map[y][z][x] = 1

        # Puzzle walls layout: clear corridors with deliberate walls forming a maze
        corridors = [
            # Horizontal corridors at z=2 and z=17
            (y, z, x) for y in range(map_layers) for x in range(1, map_size-1) for z in [2, 17]
        ] + [
            # Vertical corridors at x=2 and x=17
            (y, z, x) for y in range(map_layers) for z in range(1, map_size-1) for x in [2, 17]
        ]
        # Set corridors to 0 (open space)
        for y, z, x in corridors:
            world_map[y][z][x] = 0

        # Set maze walls (in middle positions) to 1 to create puzzle path
        maze_walls = [
            (10, 2), (10, 3), (10, 4), (11, 4), (12, 4),
            (5, 5), (6, 5), (7, 5), (7, 6), (7, 7),
            (15, 10), (16, 10), (17, 10), (12, 15), (13, 15), (14, 15)
        ]
        for y in range(map_layers - 1):  # apply only on bottom and middle layers
            for (xw, zw) in maze_walls:
                if 1 <= xw < map_size-1 and 1 <= zw < map_size-1:
                    world_map[y][zw][xw] = 1

        # Floors and ceilings
        for z in range(map_size):
            for x in range(map_size):
                world_map[0][z][x] = 1  # Floor
                world_map[map_layers-1][z][x] = 1  # Ceiling

        # Start area openings
        world_map[1][1][1] = 0
        world_map[1][1][2] = 0
        world_map[1][2][1] = 0

        # Stairs sample
        for i in range(5):
            world_map[0][5 + i][15] = 0
            world_map[1][5 + i][15] = 0
            world_map[0][5 + i][16] = 0
            world_map[1][5 + i][16] = 0

        return world_map

    def generate_items(self):
        items = []
        positions = [
            (3, 1, 3),
            (16, 1, 3),
            (10, 1, 7),
            (3, 1, 16),
            (16, 1, 16)
        ]
        for pos in positions:
            x, y, z = pos
            if self.map[y][z][x] == 0:
                items.append(pos)
        return items

    def load_textures(self):
        textures = {}

        def create_colored_texture(color):
            tex_id = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, tex_id)
            tex_data = []
            for i in range(64):
                for j in range(64):
                    if (i // 8 + j // 8) % 2 == 0:
                        tex_data.extend([int(c * 0.6) for c in color])
                    else:
                        tex_data.extend(color)
            tex_data_bytes = bytes(tex_data)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, 64, 64, 0, GL_RGB, GL_UNSIGNED_BYTE, tex_data_bytes)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            return tex_id

        textures['wall_red'] = create_colored_texture([255, 50, 50])
        textures['wall_blue'] = create_colored_texture([50, 50, 255])
        textures['wall_gray'] = create_colored_texture([150, 150, 150])

        item_tex = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, item_tex)
        tex_data = [255, 255, 0] * (16 * 16)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, 16, 16, 0, GL_RGB, GL_UNSIGNED_BYTE, bytes(tex_data))
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        textures['item'] = item_tex

        return textures

    def draw(self, player):
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_TEXTURE_2D)

        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(60, (width / height), 0.1, 50.0)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        yaw_rad = math.radians(player.rot[0])
        pitch_rad = math.radians(player.rot[1])

        cam_x = player.pos[0] + math.sin(yaw_rad)
        cam_y = player.pos[1] + math.tan(pitch_rad)
        cam_z = player.pos[2] - math.cos(yaw_rad)

        gluLookAt(player.pos[0], player.pos[1], player.pos[2],
                  cam_x, cam_y, cam_z,
                  0, 1, 0)

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        # Draw cubes per layer color
        map_layers = len(self.map)
        for y in range(map_layers):
            if y == 0:
                tex = self.textures['wall_red']
            elif y == 1:
                tex = self.textures['wall_blue']
            else:
                tex = self.textures['wall_gray']
            glBindTexture(GL_TEXTURE_2D, tex)
            for z in range(len(self.map[y])):
                for x in range(len(self.map[y][z])):
                    if self.map[y][z][x]:
                        self.draw_cube(x, y, z)

        glBindTexture(GL_TEXTURE_2D, self.textures['item'])
        for i, (x, y, z) in enumerate(self.items):
            if i < player.collected_items:
                continue
            self.draw_item(x + 0.5, y + 0.5, z + 0.5)

        # Skybox gradient
        glDisable(GL_TEXTURE_2D)
        glBegin(GL_QUADS)
        glColor3f(0.2, 0.5, 0.8)
        glVertex3f(-100, 100, -100)
        glVertex3f(100, 100, -100)
        glVertex3f(100, 100, 100)
        glVertex3f(-100, 100, 100)

        glColor3f(0.6, 0.8, 0.2)
        glVertex3f(-100, -10, -100)
        glVertex3f(100, -10, -100)
        glVertex3f(100, -10, 100)
        glVertex3f(-100, -10, 100)
        glEnd()
        glEnable(GL_TEXTURE_2D)

    def draw_cube(self, x, y, z):
        size = 1.0
        vertices = [
            [x, y, z],
            [x + size, y, z],
            [x + size, y + size, z],
            [x, y + size, z],
            [x, y, z + size],
            [x + size, y, z + size],
            [x + size, y + size, z + size],
            [x, y + size, z + size]
        ]
        faces = [
            [0, 1, 2, 3],
            [1, 5, 6, 2],
            [5, 4, 7, 6],
            [4, 0, 3, 7],
            [3, 2, 6, 7],
            [4, 5, 1, 0]
        ]
        tex_coords = [
            [0, 0], [1, 0], [1, 1], [0, 1]
        ]
        glBegin(GL_QUADS)
        for face in faces:
            for i, vertex in enumerate(face):
                glTexCoord2fv(tex_coords[i])
                glVertex3fv(vertices[vertex])
        glEnd()

    def draw_item(self, x, y, z):
        size = 0.3
        glPushMatrix()
        glTranslatef(x, y, z)
        glRotatef(pygame.time.get_ticks() / 20 % 360, 0, 1, 0)
        glBegin(GL_TRIANGLES)
        # Top pyramid
        glTexCoord2f(0.5, 1); glVertex3f(0, size, 0)
        glTexCoord2f(0, 0); glVertex3f(-size, 0, -size)
        glTexCoord2f(1, 0); glVertex3f(size, 0, -size)

        glTexCoord2f(0.5, 1); glVertex3f(0, size, 0)
        glTexCoord2f(1, 0); glVertex3f(size, 0, -size)
        glTexCoord2f(1, 0); glVertex3f(size, 0, size)

        glTexCoord2f(0.5, 1); glVertex3f(0, size, 0)
        glTexCoord2f(1, 0); glVertex3f(size, 0, size)
        glTexCoord2f(0, 0); glVertex3f(-size, 0, size)

        glTexCoord2f(0.5, 1); glVertex3f(0, size, 0)
        glTexCoord2f(0, 0); glVertex3f(-size, 0, size)
        glTexCoord2f(0, 0); glVertex3f(-size, 0, -size)

        # Bottom pyramid
        glTexCoord2f(0.5, 1); glVertex3f(0, -size, 0)
        glTexCoord2f(0, 0); glVertex3f(-size, 0, -size)
        glTexCoord2f(1, 0); glVertex3f(size, 0, -size)

        glTexCoord2f(0.5, 1); glVertex3f(0, -size, 0)
        glTexCoord2f(1, 0); glVertex3f(size, 0, -size)
        glTexCoord2f(1, 0); glVertex3f(size, 0, size)

        glTexCoord2f(0.5, 1); glVertex3f(0, -size, 0)
        glTexCoord2f(1, 0); glVertex3f(size, 0, size)
        glTexCoord2f(0, 0); glVertex3f(-size, 0, size)

        glTexCoord2f(0.5, 1); glVertex3f(0, -size, 0)
        glTexCoord2f(0, 0); glVertex3f(-size, 0, size)
        glTexCoord2f(0, 0); glVertex3f(-size, 0, -size)
        glEnd()
        glPopMatrix()

    def check_item_collision(self, player):
        collected = []
        for i, (x, y, z) in enumerate(self.items):
            if i >= player.collected_items:
                dist = math.sqrt((player.pos[0] - (x + 0.5)) ** 2 +
                                 (player.pos[1] - (y + 0.5)) ** 2 +
                                 (player.pos[2] - (z + 0.5)) ** 2)
                if dist < 0.7:
                    collected.append(i)

        if collected:
            player.collected_items += len(collected)
            return True
        return False

# Game state
class GameState:
    PLAYING = 0
    WON = 1
    LOST = 2

# Main game function
def main():
    pygame.mouse.set_visible(False)
    pygame.event.set_grab(True)

    player = Player()
    world = World()
    game_state = GameState.PLAYING

    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    glLightfv(GL_LIGHT0, GL_POSITION, [1, 1, 1, 0])
    glLightfv(GL_LIGHT0, GL_DIFFUSE, [1, 1, 1, 1])
    glLightfv(GL_LIGHT0, GL_AMBIENT, [0.2, 0.2, 0.2, 1])

    glMaterialfv(GL_FRONT, GL_DIFFUSE, [0.8, 0.8, 0.8, 1])
    glMaterialfv(GL_FRONT, GL_SPECULAR, [0.5, 0.5, 0.5, 1])
    glMaterialfv(GL_FRONT, GL_SHININESS, 50)

    clock = pygame.time.Clock()
    running = True

    while running:
        dt = clock.tick(MAX_FPS) / 1000.0  # Limit FPS to 60, dt unused but can be for physics step

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
            elif event.type == pygame.MOUSEMOTION and game_state == GameState.PLAYING:
                player.handle_mouse(event.rel[0], event.rel[1])

        if game_state == GameState.PLAYING:
            player.update_position(world)

            if world.check_item_collision(player):
                print(f"Collected {player.collected_items} items!")

            if player.collected_items >= len(world.items):
                game_state = GameState.WON
                print("You collected all items and won the game!")

        # Render
        world.draw(player)

        # Draw HUD
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        gluOrtho2D(0, width, height, 0)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()

        glDisable(GL_LIGHTING)
        glDisable(GL_DEPTH_TEST)

        glColor3f(1, 1, 1)
        glBegin(GL_LINES)
        glVertex2f(width//2 - 10, height//2)
        glVertex2f(width//2 + 10, height//2)
        glVertex2f(width//2, height//2 - 10)
        glVertex2f(width//2, height//2 + 10)
        glEnd()

        font = pygame.font.SysFont('Arial', 30)
        text = font.render(f"Items: {player.collected_items}/{len(world.items)}", True, (255, 255, 255))
        text_data = pygame.image.tostring(text, "RGBA", True)
        glRasterPos2d(20, 20)
        glDrawPixels(text.get_width(), text.get_height(), GL_RGBA, GL_UNSIGNED_BYTE, text_data)

        if game_state != GameState.PLAYING:
            if game_state == GameState.WON:
                msg = "You Won! Collected all items."
                color = (0, 255, 0)
            else:
                msg = "Game Over"
                color = (255, 0, 0)

            font = pygame.font.SysFont('Arial', 50)
            text = font.render(msg, True, color)
            text_data = pygame.image.tostring(text, "RGBA", True)
            glRasterPos2d(width//2 - text.get_width()//2, height//2 - text.get_height()//2)
            glDrawPixels(text.get_width(), text.get_height(), GL_RGBA, GL_UNSIGNED_BYTE, text_data)

        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()

        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()

