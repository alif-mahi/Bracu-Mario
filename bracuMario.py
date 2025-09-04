from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
import random
import math
import time

# =========================
# Global Game State
# =========================

# Camera-related variables
fovY = 60
GRID_LENGTH = 600
GRID_SIZE = 10
CELL_SIZE = GRID_LENGTH // GRID_SIZE
rand_var = 423

target_fps = 60
frame_time = 1000 // target_fps  # milliseconds per frame
last_time = 0

# Player (linear path: X only) & jump
player_pos = [0.0, 0.0]   # now y will be used for forward/backward movement
player_angle = 0.0
player_speed = 6.0
player_radius = 12.0       # made Mario smaller (was 18.0)
player_z = 40.0            # player base height from ground when standing on flat floor
player_vz = 0.0            # vertical velocity
gravity = -0.8             # reduced gravity for smoother jumps (was -1.2)
jump_speed = 18.0          # reduced for smoother jumps (was 22.0)
long_jump_speed = 24.0     # reduced for smoother jumps (was 28.0)
long_jump_forward = 25.0   # forward momentum for long jump
on_ground = False
is_long_jumping = False    # track if doing long jump
long_jump_momentum = 0.0   # remaining forward momentum

# Key states for combo inputs
keys_pressed = set()       # track currently pressed keys

# Bullets — not used in this game, kept to respect template structure
bullets = []
bullet_speed = 20.0
bullet_cooldown_frames = 6
bullet_cooldown = 0
missed_bullets = 0

# Enemies (patrolling along X on platforms)
random.seed(rand_var)
ENEMY_COUNT = 6
enemies = []
enemy_speed = 0.6

# Coins
COIN_COUNT = 30
coins = []
coin_spin = 0.0
coins_collected = 0

# Platforms (procedurally generated linear segments along X)
platforms = []  # each: {"x1":..., "x2":..., "z":..., "w":..., "d":...}

# Camera control & modes
cam_theta = 30.0
cam_height = 180.0
cam_radius = 350.0
first_person = False

# Cheat modes (not used beyond display toggles; left for template parity)
cheat_mode = False
cheat_v_follow = False

# Game status
life = 100
score = 0
game_over = False
start_time = time.time()

damage_flash = 0.0  # for red flash when taking damage
last_score_bonus = 0  # track score milestones for extra lives

# Day-Night
day_night_t = 0.0  # 0..1 cycles
is_day = True      # added manual day/night control

# Particles (for coin pickups)
particles = []  # each: {"x","y","z","vx","vy","vz","life","type"}

# =========================
# Utility
# =========================

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def deg_to_rad(a):
    return a * math.pi / 180.0

def normalize(dx, dy):
    l = math.sqrt(dx * dx + dy * dy)
    if l == 0:
        return 0.0, 0.0
    return dx / l, dy / l

def dist2(ax, ay, bx, by):
    dx, dy = ax - bx, ay - by
    return dx * dx + dy * dy

# =========================
# World Initialization
# =========================

def gen_platforms():
    global platforms
    random.seed(rand_var)
    platforms = []
    x = -GRID_LENGTH + 80
    while x < GRID_LENGTH - 80:
        seg_len = random.randint(100, 220)
        gap = random.randint(40, 120)
        height = random.choice([0, 20, 40, 60, 80])  # lower heights (was 0, 30, 60, 90, 120, 150)
        platforms.append({
            "x1": x,
            "x2": x + seg_len,
            "z": height,
            "w": seg_len,
            "d": 80
        })
        x += seg_len + gap
    # Ensure a start platform around x=0
    platforms.append({
        "x1": -80, "x2": 120, "z": 40, "w": 200, "d": 100  # lower start platform (was z: 60)
    })

def place_coins():
    global coins
    coins = []
    placed = 0
    attempts = 0
    while placed < COIN_COUNT and attempts < 1000:
        attempts += 1
        p = random.choice(platforms)
        cx = random.uniform(p["x1"] + 20, p["x2"] - 20)
        cy = 0.0  # horizontal middle point, same orientation as Mario and enemies
        
        coin_height_type = random.choice(["platform", "low_jump", "high_jump"])
        if coin_height_type == "platform":
            cz = p["z"] + 25  # just above platform surface, easy to collect
        elif coin_height_type == "low_jump":
            cz = p["z"] + 45  # requires small jump to collect
        else:  # high_jump
            cz = p["z"] + 70  # requires full jump to collect
            
        coins.append({"x": cx, "y": cy, "z": cz, "taken": False})
        placed += 1

def init_enemies():
    global enemies
    enemies = []
    available_platforms = [p for p in platforms if p["w"] > 80]  # only use larger platforms
    
    for i in range(min(ENEMY_COUNT, len(available_platforms))):
        p = available_platforms[i]
        ex = (p["x1"] + p["x2"]) / 2.0  # center of platform
        ey = 0.0    # horizontal middle point, same as Mario
        ez = p["z"] + 15.0              # on platform surface
        
        too_close = False
        for existing in enemies:
            dist = math.sqrt((ex - existing["x"])**2 + (ey - existing["y"])**2)
            if dist < 100:  # reduced minimum distance for platform placement
                too_close = True
                break
        
        if not too_close:
            dir_sign = random.choice([-1.0, 1.0])
            enemies.append({
                "x": ex,
                "y": ey,
                "z": ez,
                "r": 12.0,  # increased enemy size from 8.0 to 12.0
                "speed": enemy_speed * dir_sign,
                "patrol_center_x": ex,
                "patrol_center_y": 0.0,  # horizontal middle point
                "patrol_radius": min(30, (p["x2"] - p["x1"]) / 4),  # patrol within platform bounds
                "platform": p,  # reference to platform
                "alive": True,
                "squash": 1.0
            })

# =========================
# Drawing Helpers
# =========================

def draw_text(x, y, text, font = GLUT_BITMAP_HELVETICA_18):
    glColor3f(1, 1, 1)
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, 1000, 0, 800)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    glRasterPos2f(x, y)
    for ch in text:
        glutBitmapCharacter(font, ord(ch))
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

def draw_checker_floor():
    glBegin(GL_QUADS)
    for i in range(-GRID_SIZE, GRID_SIZE):
        for j in range(-GRID_SIZE, GRID_SIZE):
            x1 = i * CELL_SIZE
            y1 = j * CELL_SIZE
            x2 = (i + 1) * CELL_SIZE
            y2 = (j + 1) * CELL_SIZE
            if (i + j) % 2 == 0:
                glColor3f(0.3, 0.34, 0.4)
            else:
                glColor3f(0.2, 0.22, 0.27)
            glVertex3f(x1, y1, 0)
            glVertex3f(x2, y1, 0)
            glVertex3f(x2, y2, 0)
            glVertex3f(x1, y2, 0)
    glEnd()

def draw_platforms():
    for p in platforms:
        glPushMatrix()
        c = 0.5 + 0.7 * (p["z"] / 180.0)
        glColor3f(0.4 + 0.3 * c, 0.2 + 0.4 * c, 0.1 + 0.2 * c)
        
        # draw main platform
        cx = (p["x1"] + p["x2"]) / 2.0
        glTranslatef(cx, 0.0, p["z"] / 2.0)
        glScalef(p["w"], 80, p["z"] if p["z"] > 4 else 4)
        glutSolidCube(1.0)
        glPopMatrix()
        
        glColor3f(0.2, 0.15, 0.1)
        glPushMatrix()
        glTranslatef(cx, 0.0, p["z"] + 2)
        glScalef(p["w"] + 4, 84, 4)
        glutSolidCube(1.0)
        glPopMatrix()

def draw_coin(c):
    if c["taken"]:
        return
    glPushMatrix()
    glTranslatef(c["x"], c["y"], c["z"])
    dn = 0.5 + 0.5 * math.sin(day_night_t * 6.28318530718)
    pulse = 0.8 + 0.2 * math.sin(coin_spin * 0.1)
    glColor3f(1.0 * pulse, (0.85 + 0.14 * dn) * pulse, (0.2 + 0.2 * dn) * pulse)
    glRotatef(coin_spin, 0, 0, 1)
    glScalef(12, 12, 3)  # slightly smaller coin
    glutSolidCube(1)
    
    glColor3f(1.0, 1.0, 0.8)
    glScalef(0.7, 0.7, 0.7)
    glutSolidCube(1)
    glPopMatrix()

def draw_enemy(e):
    if not e["alive"]:
        return
    glPushMatrix()
    glTranslatef(e["x"], e["y"], e["z"])
    glScalef(1.0, 1.0, e["squash"])
    
    # body (red with darker outline)
    glColor3f(0.8, 0.1, 0.1)
    glutSolidSphere(e["r"], 12, 12)
    
    # darker outline
    glColor3f(0.4, 0.05, 0.05)
    glutWireSphere(e["r"] * 1.05, 12, 12)
    
    # head (black with eyes)
    glTranslatef(0, 0, e["r"] * 0.8)
    glColor3f(0.0, 0.0, 0.0)
    glutSolidSphere(e["r"] * 0.5, 16, 16)
    glPopMatrix()

    # simple eyes
    glColor3f(1.0, 1.0, 1.0)
    glPushMatrix()
    glTranslatef(-e["r"] * 0.2, -e["r"] * 0.3, e["r"] * 0.2)
    glutSolidSphere(e["r"] * 0.1, 6, 6)
    glPopMatrix()
    glPushMatrix()
    glTranslatef(e["r"] * 0.2, -e["r"] * 0.3, e["r"] * 0.2)
    glutSolidSphere(e["r"] * 0.1, 6, 6)
    glPopMatrix()

def draw_player():
    glPushMatrix()
    glTranslatef(player_pos[0], player_pos[1], player_z)  # include Y position

    # torso (Mario's shirt - red)
    torso_height = 32  # increased from 24
    torso_width = 24   # increased from 18
    torso_depth = 18   # increased from 14
    glPushMatrix()
    glColor3f(0.8, 0.1, 0.1)  # Mario red
    glTranslatef(0, 0, torso_height / 2.0)
    glScalef(torso_width, torso_depth, torso_height)
    glutSolidCube(1)
    glPopMatrix()

    # overalls (blue)
    glPushMatrix()
    glColor3f(0.1, 0.1, 0.8)
    glTranslatef(0, 0, torso_height / 3.0)
    glScalef(torso_width * 0.9, torso_depth * 1.1, torso_height * 0.8)
    glutSolidCube(1)
    glPopMatrix()

    # head (peach colored) - made bigger
    glPushMatrix()
    glColor3f(0.9, 0.7, 0.6)
    glTranslatef(0, 0, torso_height + 10)  # adjusted for bigger torso
    glutSolidSphere(10, 16, 16)  # increased from 8
    glPopMatrix()

    # hat (red) - made bigger
    glPushMatrix()
    glColor3f(0.8, 0.1, 0.1)
    glTranslatef(0, 0, torso_height + 15)  # adjusted for bigger head
    glScalef(12, 12, 5)  # increased from 10, 10, 4
    glutSolidCube(1)
    glPopMatrix()

    # legs (blue) - positioned at the bottom to touch the ground, made bigger
    for side in [-1, 1]:
        glPushMatrix()
        glColor3f(0.1, 0.1, 0.7)
        glTranslatef(side * 5, 0, -10)  # adjusted spacing and position
        gluCylinder(gluNewQuadric(), 4, 3.5, 15, 8, 1)  # increased size
        glTranslatef(0, 0, 15)
        gluCylinder(gluNewQuadric(), 3.5, 3, 12, 8, 1)  # increased size
        glPopMatrix()
    
    # mustache - made bigger
    glPushMatrix()
    glColor3f(0.3, 0.2, 0.1)
    glTranslatef(0, -8, torso_height + 8)  # adjusted for bigger head
    glScalef(8, 3, 1.5)  # increased from 6, 2, 1
    glutSolidCube(1)
    glPopMatrix()
    
    glPopMatrix()

def draw_particles():
    glBegin(GL_QUADS)
    for p in particles:
        # fade color with life
        life01 = clamp(p["life"] / 40.0, 0.0, 1.0)
        
        if p["type"] == "coin":
            glColor3f(1.0, 0.9 * life01, 0.3 * life01)
        elif p["type"] == "enemy":
            glColor3f(0.8 * life01, 0.1 * life01, 0.1 * life01)
        else:
            glColor3f(1.0, 0.9 * life01, 0.3 * life01)
            
        s = 4 + 8 * (1.0 - life01)
        x = p["x"]; y = p["y"]; z = p["z"]
        # billboarded-ish small quad (axis-aligned since we avoid complex math)
        glVertex3f(x - s, y - s, z)
        glVertex3f(x + s, y - s, z)
        glVertex3f(x + s, y + s, z)
        glVertex3f(x - s, y + s, z)
    glEnd()

# =========================
# Input Handlers
# =========================

def keyboardListener(key, x, y):
    global player_angle, cheat_mode, cheat_v_follow, player_pos, first_person, keys_pressed
    global is_day, day_night_t

    if game_over:
        if key == b'r' or key == b'R':
            restart_game()
        return

    key_str = key.decode('utf-8').lower()
    keys_pressed.add(key_str)

    if key_str == 'a':
        new_x = player_pos[0] - player_speed  # move left across platform
        if not is_movement_blocked(new_x, player_pos[1], player_z):
            player_pos[0] = new_x
            clamp_player_within_grid_linear()
    elif key_str == 'd':
        new_x = player_pos[0] + player_speed  # move right across platform
        if not is_movement_blocked(new_x, player_pos[1], player_z):
            player_pos[0] = new_x
            clamp_player_within_grid_linear()
    elif key_str == ' ':
        if 'a' in keys_pressed or 'd' in keys_pressed:
            do_long_jump()  # Long jump when A or D is held
        else:
            do_jump()  # Regular jump
    elif key_str == 'l':
        if not is_day:
            is_day = True
            day_night_t = 0.8
    elif key_str == 'n':
        if is_day:
            is_day = False
            day_night_t = 0.2
    elif key_str == 'c':
        cheat_mode = not cheat_mode
    elif key_str == 'v':
        first_person = not first_person
    elif key_str == 'r':
        restart_game()

    glutPostRedisplay()

def keyboardUpListener(key, x, y):
    global keys_pressed
    key_str = key.decode('utf-8').lower()
    keys_pressed.discard(key_str)

def specialKeyListener(key, x, y):
    global cam_theta, cam_height
    if key == GLUT_KEY_UP:
        cam_height = clamp(cam_height + 15.0, 120.0, 1400.0)
    elif key == GLUT_KEY_DOWN:
        cam_height = clamp(cam_height - 15.0, 60.0, 1400.0)
    elif key == GLUT_KEY_LEFT:
        cam_theta += 3.0
    elif key == GLUT_KEY_RIGHT:
        cam_theta -= 3.0
    glutPostRedisplay()

def mouseListener(button, state, x, y):
    # No shooting/mouse actions in this Mario-like version.
    pass

# =========================
# Camera
# =========================

def setupCamera():
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(fovY, 1.25, 0.1, 3000)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()

    if first_person:
        eye_height = player_z + 15  # eye level
        look_ahead = 50
        gluLookAt(player_pos[0], player_pos[1], eye_height,
                  player_pos[0] + look_ahead, player_pos[1], eye_height - 5,
                  0, 0, 1)
    else:
        # Third person follow camera
        cam_x = player_pos[0] + cam_radius * math.cos(deg_to_rad(cam_theta))
        cam_y = player_pos[1] + cam_radius * math.sin(deg_to_rad(cam_theta))
        cam_z = cam_height
        
        gluLookAt(cam_x, cam_y, cam_z,
                  player_pos[0], player_pos[1], player_z,
                  0, 0, 1)

# =========================
# Game Mechanics
# =========================

def clamp_player_within_grid_linear():
    global player_pos
    player_pos[0] = clamp(player_pos[0], -GRID_LENGTH * 2, GRID_LENGTH * 2)
    player_pos[1] = clamp(player_pos[1], -GRID_LENGTH * 2, GRID_LENGTH * 2)

def current_ground_z_at_xy(x, y):  # updated to handle both x and y coordinates
    max_z = 0.0  # floor level
    for p in platforms:
        if p["x1"] <= x <= p["x2"] and -40 <= y <= 40:  # platforms have some Y width
            max_z = max(max_z, p["z"])
    return max_z

def current_ground_z_at_x(x):  # keep for compatibility, use player Y position
    return current_ground_z_at_xy(x, player_pos[1])

def do_jump():
    global player_vz, on_ground
    if on_ground:
        player_vz = jump_speed
        on_ground = False

def do_long_jump():
    global player_vz, on_ground, is_long_jumping, long_jump_momentum
    if on_ground:
        player_vz = long_jump_speed
        on_ground = False
        is_long_jumping = True
        if 'a' in keys_pressed:
            long_jump_momentum = -long_jump_forward * 1.2  # jump left
        elif 'd' in keys_pressed:
            long_jump_momentum = long_jump_forward * 1.2   # jump right
        else:
            long_jump_momentum = long_jump_forward * 1.2   # default right

def update_player_physics():
    global player_z, player_vz, on_ground, is_long_jumping, long_jump_momentum, player_pos
    
    player_vz += gravity
    new_z = player_z + player_vz
    
    if is_long_jumping and abs(long_jump_momentum) > 0:
        momentum_step = long_jump_momentum * 0.15
        new_x = player_pos[0] + momentum_step
        collision, _ = check_platform_collision(new_x, player_pos[1], player_z)
        if not collision:
            player_pos[0] = new_x
            clamp_player_within_grid_linear()
        long_jump_momentum *= 0.92  # slower decay for longer jumps
        if abs(long_jump_momentum) < 2.0:  # higher threshold
            is_long_jumping = False
            long_jump_momentum = 0.0
    
    ground_z = current_ground_z_at_xy(player_pos[0], player_pos[1])
    base_height = ground_z + 12.0  # Mario's feet touch the platform, accounting for leg height
    
    collision, platform = check_platform_collision(player_pos[0], player_pos[1], new_z)
    
    if new_z <= base_height:
        player_z = base_height
        player_vz = 0.0
        on_ground = True
        is_long_jumping = False
        long_jump_momentum = 0.0
    elif collision and player_vz < 0:
        if platform:
            player_z = platform["z"] + 12.0  # feet touch platform surface
            player_vz = 0.0
            on_ground = True
    else:
        player_z = new_z
        on_ground = False
        
        if player_z < 12.0:  # below ground level
            player_z = 12.0
            player_vz = 0.0
            on_ground = True

def update_enemies():
    for e in enemies:
        if not e["alive"]:
            continue
            
        if "platform" in e:
            p = e["platform"]
            e["x"] += e["speed"]
            
            if e["x"] <= p["x1"] + 20 or e["x"] >= p["x2"] - 20:
                e["speed"] *= -1
            
            e["x"] = max(p["x1"] + 20, min(p["x2"] - 20, e["x"]))
            e["y"] = 0.0  # stay at horizontal middle point
            e["z"] = p["z"] + 15.0  # stay on platform surface
        else:
            angle = time.time() * e["speed"] * 0.5
            e["x"] = e["patrol_center_x"] + math.cos(angle) * e["patrol_radius"]
            e["y"] = 0.0  # horizontal middle point
            e["z"] = current_ground_z_at_xy(e["x"], e["y"]) + 12.0
            
        if e["squash"] < 1.0:
            e["squash"] = min(1.0, e["squash"] + 0.1)

def spawn_particles(x, y, z, n=10, particle_type="coin"):
    global particles
    for _ in range(n):
        if particle_type == "coin":
            particles.append({
                "x": x + random.uniform(-15, 15),
                "y": y + random.uniform(-15, 15),
                "z": z + random.uniform(-5, 20),
                "vx": random.uniform(-3, 3),
                "vy": random.uniform(-3, 3),
                "vz": random.uniform(3, 10),
                "life": 40,
                "type": "coin"
            })
        elif particle_type == "enemy":
            particles.append({
                "x": x + random.uniform(-20, 20),
                "y": y + random.uniform(-20, 20),
                "z": z + random.uniform(0, 25),
                "vx": random.uniform(-4, 4),
                "vy": random.uniform(-4, 4),
                "vz": random.uniform(5, 12),
                "life": 35,
                "type": "enemy"
            })

def update_particles():
    global particles
    for p in particles[:]:  # copy list to avoid modification during iteration
        p["x"] += p["vx"]
        p["y"] += p["vy"]
        p["z"] += p["vz"]
        p["vz"] -= 0.3  # gravity on particles
        p["life"] -= 1
        
        if p["life"] <= 0:
            particles.remove(p)

def collect_coins():
    global coins_collected, score
    for c in coins:
        if c["taken"]:
            continue
        if abs(player_pos[0] - c["x"]) <= 20 and abs(player_pos[1] - c["y"]) <= 20 and abs(player_z - c["z"]) <= 28:
            c["taken"] = True
            coins_collected += 1
            score += 10
            spawn_particles(c["x"], c["y"], c["z"], n=15, particle_type="coin")

def life_down(dmg=20):
    global life, game_over, damage_flash
    life -= dmg
    damage_flash = 30.0  # flash duration
    if life <= 0:
        life = 0
        game_over = True

def enemy_interactions():
    global score, player_vz
    
    for e in enemies:
        if not e["alive"]:
            continue
            
        dx = player_pos[0] - e["x"]
        dy = player_pos[1] - e["y"]  # include Y distance
        dz = player_z - e["z"]
        
        distance_2d = math.sqrt(dx*dx + dy*dy)  # 2D distance check
        
        if distance_2d <= (player_radius + e["r"]) and abs(dz) <= 25:
            if player_vz < 0 and player_z > e["z"] + 10:
                e["alive"] = False
                e["squash"] = 0.3  # squash effect
                score += 50
                player_vz = jump_speed * 0.6  # bounce off enemy
                spawn_particles(e["x"], e["y"], e["z"], n=20, particle_type="enemy")
            else:
                life_down(20)
                if distance_2d > 0:
                    knockback_x = (dx / distance_2d) * 30
                    knockback_y = (dy / distance_2d) * 30
                    player_pos[0] += knockback_x
                    player_pos[1] += knockback_y
                clamp_player_within_grid_linear()

def maybe_award_extra_life():
    global life, score, last_score_bonus
    current_milestone = score // 500
    if current_milestone > last_score_bonus and life < 100:
        life = min(100, life + 20)
        last_score_bonus = current_milestone
        spawn_particles(player_pos[0], player_pos[1], player_z + 20, n=25, particle_type="coin")

# =========================
# Idle Loop
# =========================

def idle():
    global bullet_cooldown, game_over, missed_bullets, coin_spin, day_night_t, damage_flash
    global last_time

    current_time = glutGet(GLUT_ELAPSED_TIME)
    if current_time - last_time < frame_time:
        return
    last_time = current_time

    if bullet_cooldown > 0:
        bullet_cooldown -= 1

    if damage_flash > 0:
        damage_flash -= 1.0

    if not game_over:
        update_player_physics()
        update_enemies()
        collect_coins()
        enemy_interactions()
        update_particles()
        maybe_award_extra_life()

        coin_spin = (coin_spin + 2.0) % 360.0

    glutPostRedisplay()

# =========================
# Rendering
# =========================

def showScreen():
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    
    dn = 0.5 + 0.5 * math.sin(day_night_t * 6.28318530718)
    sky = 0.05 + 0.20 * dn
    
    if damage_flash > 0:
        flash_intensity = damage_flash / 30.0
        glClearColor(sky * 0.5 + flash_intensity * 0.5, sky * 0.7, sky, 1)
    else:
        glClearColor(sky * 0.5, sky * 0.7, sky, 1)
        
    glLoadIdentity()
    glViewport(0, 0, 1000, 800)

    setupCamera()

    glShadeModel(GL_SMOOTH)

    draw_checker_floor()
    draw_platforms()

    for c in coins:
        draw_coin(c)

    for e in enemies:
        draw_enemy(e)

    draw_player()
    
    draw_particles()

    elapsed = int(time.time() - start_time)
    
    glColor3f(1.0, 1.0, 1.0)
    draw_text(10, 770, f"SCORE: {score:,}", GLUT_BITMAP_HELVETICA_18)
    
    life_color = (1.0, 0.2, 0.2) if life <= 20 else (1.0, 0.8, 0.2) if life <= 50 else (0.2, 1.0, 0.2)
    glColor3f(*life_color)
    draw_text(10, 745, f"LIFE: {life}/100", GLUT_BITMAP_HELVETICA_18)
    
    glColor3f(0.8, 0.8, 1.0)
    draw_text(10, 720, f"COINS: {coins_collected}/{COIN_COUNT}")
    draw_text(10, 695, f"TIME: {elapsed:,}s")
    
    glColor3f(0.6, 0.9, 0.6)
    draw_text(10, 670, f"Next Life: {((score // 500) + 1) * 500 - score} pts")
    
    glColor3f(0.7, 0.7, 0.9)
    draw_text(10, 180, "=== CONTROLS ===")
    draw_text(10, 160, "A/D - Move Left/Right")
    draw_text(10, 140, "Space - Jump")
    draw_text(10, 120, "A/D+Space - Long Jump")
    draw_text(10, 100, "L/N - Day/Night Toggle")
    draw_text(10, 80, "Arrow Keys - Camera")
    draw_text(10, 60, "V - First Person | R - Restart")

    if game_over:
        glColor3f(1.0, 0.3, 0.3)
        draw_text(350, 450, "=== GAME OVER ===", GLUT_BITMAP_TIMES_ROMAN_24)
        glColor3f(1.0, 1.0, 1.0)
        draw_text(380, 400, f"Final Score: {score:,}")
        draw_text(370, 370, f"Coins Collected: {coins_collected}/{COIN_COUNT}")
        draw_text(380, 340, f"Survival Time: {elapsed:,}s")
        glColor3f(0.8, 0.8, 1.0)
        draw_text(400, 300, "Press R to Restart")

    glFlush()
    glutSwapBuffers()

# =========================
# OpenGL / GLUT Setup
# =========================

def init_gl():
    glClearColor(0.05, 0.06, 0.09, 1)
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    glEnable(GL_COLOR_MATERIAL)
    glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
    
    glShadeModel(GL_SMOOTH)
    glEnable(GL_NORMALIZE)
    glHint(GL_PERSPECTIVE_CORRECTION_HINT, GL_NICEST)
    
    light_pos = [0.0, 0.0, 500.0, 1.0]
    light_ambient = [0.3, 0.3, 0.4, 1.0]
    light_diffuse = [0.8, 0.8, 0.9, 1.0]
    
    glLightfv(GL_LIGHT0, GL_POSITION, light_pos)
    glLightfv(GL_LIGHT0, GL_AMBIENT, light_ambient)
    glLightfv(GL_LIGHT0, GL_DIFFUSE, light_diffuse)

def restart_game():
    global player_pos, player_angle, bullets, missed_bullets, score, life, game_over
    global cheat_mode, cheat_v_follow, first_person
    global player_z, player_vz, on_ground, start_time
    global coins_collected, particles, is_long_jumping, long_jump_momentum, keys_pressed
    global damage_flash, last_score_bonus

    player_pos = [0.0, 0.0]
    player_angle = 0.0
    bullets = []
    missed_bullets = 0
    score = 0
    life = 100
    game_over = False
    cheat_mode = False
    cheat_v_follow = False
    first_person = False
    player_z = 40.0
    player_vz = 0.0
    on_ground = True
    coins_collected = 0
    particles = []
    is_long_jumping = False
    long_jump_momentum = 0.0
    keys_pressed = set()
    damage_flash = 0.0
    last_score_bonus = 0
    start_time = time.time()

    gen_platforms()
    place_coins()
    init_enemies()

# =========================
# Collision Detection
# =========================

def is_movement_blocked(new_x, new_y, new_z):
    for p in platforms:
        if (p["x1"] - 5 <= new_x <= p["x2"] + 5 and 
            -80 <= new_y <= 80):
            # If Mario is standing on top of the platform (within reasonable height), allow movement
            if p["z"] + 8 <= new_z <= p["z"] + 30:
                continue  # Allow movement on platform surface
            # Block movement if trying to go through platform from sides or below
            elif p["z"] <= new_z <= p["z"] + 50:
                return True
    return False

def is_inside_platform(x, y, z):
    for p in platforms:
        if (p["x1"] <= x <= p["x2"] and 
            -40 <= y <= 40 and
            0 <= z <= p["z"] + 4):
            return True, p
    return False, None

def check_platform_collision(new_x, new_y, new_z):
    inside, platform = is_inside_platform(new_x, new_y, new_z)
    if inside:
        return True, platform
    
    for p in platforms:
        closest_x = max(p["x1"], min(new_x, p["x2"]))
        closest_y = max(-40, min(new_y, 40))
        
        dx = new_x - closest_x
        dy = new_y - closest_y
        distance_2d = math.sqrt(dx*dx + dy*dy)
        
        if (distance_2d <= player_radius and 
            new_z >= p["z"] - 5 and new_z <= p["z"] + 45):
            return True, p
    
    return False, None

# =========================
# Main Entry Point
# =========================

def main():
    try:
        import sys
        glutInit(sys.argv)
        
        try:
            glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH | GLUT_MULTISAMPLE)
        except:
            try:
                glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
            except:
                glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB)
                print("Warning: Using basic display mode")
        
        glutInitWindowSize(1000, 800)
        glutInitWindowPosition(100, 100)
        
        window = glutCreateWindow(b"BRACU Mario - Linear 3D Platformer")
        if not window:
            raise Exception("Failed to create GLUT window")
            
    except Exception as e:
        print(f"GLUT initialization failed: {e}")
        print("Please ensure you have OpenGL and GLUT properly installed.")
        print("Try installing: pip install PyOpenGL PyOpenGL_accelerate")
        return

    try:
        init_gl()
        restart_game()

        glutDisplayFunc(showScreen)
        glutKeyboardFunc(keyboardListener)
        glutKeyboardUpFunc(keyboardUpListener)
        glutSpecialFunc(specialKeyListener)
        glutMouseFunc(mouseListener)
        glutIdleFunc(idle)

        print("Mario game initialized successfully!")
        print("Controls: A/D to move, Space to jump, A/D+Space for long jump")
        glutMainLoop()
        
    except Exception as e:
        print(f"Game initialization failed: {e}")
        return

if __name__ == "__main__":
    main()
