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

# Player (linear path: X only) & jump
player_pos = [0.0, 0.0]   # y stays 0.0; we keep for compatibility but won't use y
player_angle = 0.0
player_speed = 6.0
player_radius = 18.0       # collision radius in X
player_z = 40.0            # player base height from ground when standing on flat floor
player_vz = 0.0            # vertical velocity
gravity = -1.2             # gravity acceleration
jump_speed = 22.0
on_ground = False

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

# Day-Night
day_night_t = 0.0  # 0..1 cycles

# Particles (for coin pickups)
particles = []  # each: {"x","y","z","vx","vy","vz","life"}

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
    # Start from -GRID_LENGTH to +GRID_LENGTH with random gaps and heights
    x = -GRID_LENGTH + 80
    while x < GRID_LENGTH - 80:
        seg_len = random.randint(100, 220)
        gap = random.randint(40, 120)
        height = random.choice([0, 30, 60, 90, 120, 150])
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
        "x1": -80, "x2": 120, "z": 60, "w": 200, "d": 100
    })

def place_coins():
    global coins
    coins = []
    placed = 0
    attempts = 0
    while placed < COIN_COUNT and attempts < 1000:
        attempts += 1
        p = random.choice(platforms)
        cx = random.uniform(p["x1"] + 15, p["x2"] - 15)
        cz = p["z"] + 40 + random.uniform(0, 20)
        # Keep coins near the linear path (y ~ 0)
        coins.append({"x": cx, "y": 0.0, "z": cz, "taken": False})
        placed += 1

def init_enemies():
    global enemies
    enemies = []
    # Choose some platforms to host enemies
    candidate_platforms = [p for p in platforms if p["w"] >= 120]
    random.shuffle(candidate_platforms)
    for i in range(min(ENEMY_COUNT, len(candidate_platforms))):
        p = candidate_platforms[i]
        ex = random.uniform(p["x1"] + 20, p["x2"] - 20)
        dir_sign = random.choice([-1.0, 1.0])
        enemies.append({
            "x": ex,
            "y": 0.0,
            "z": p["z"] + 18.0,
            "r": 16.0,
            "speed": enemy_speed * dir_sign,
            "x1": p["x1"] + 10,  # patrol bounds
            "x2": p["x2"] - 10,
            "alive": True,
            "squash": 1.0
        })

# =========================
# Drawing Helpers
# =========================

def draw_text(x, y, text, font=GLUT_BITMAP_HELVETICA_18):
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
        # soft color by height
        c = 0.3 + 0.7 * (p["z"] / 180.0)
        glColor3f(0.2 + 0.2 * c, 0.55 * c, 0.2 + 0.15 * c)
        # draw as stretched cube
        cx = (p["x1"] + p["x2"]) / 2.0
        glTranslatef(cx, 0.0, p["z"] / 2.0)
        glScalef(p["w"], 80, p["z"] if p["z"] > 4 else 4)
        glutSolidCube(1.0)
        glPopMatrix()

def draw_coin(c):
    if c["taken"]:
        return
    glPushMatrix()
    glTranslatef(c["x"], c["y"], c["z"])
    # glow-ish color varies with day-night
    dn = 0.5 + 0.5 * math.sin(day_night_t * 6.28318530718)
    glColor3f(1.0, 0.85 + 0.14 * dn, 0.2 + 0.2 * dn)
    glRotatef(coin_spin, 0, 0, 1)
    glScalef(14, 14, 4)  # thin coin
    glutSolidCube(1)
    glPopMatrix()

def draw_enemy(e):
    if not e["alive"]:
        return
    glPushMatrix()
    glTranslatef(e["x"], e["y"], e["z"])
    # body (red) + head (black), squash when stomped (brief)
    glScalef(1.0, 1.0, e["squash"])
    glColor3f(0.9, 0.1, 0.1)
    glutSolidSphere(e["r"], 16, 16)
    glTranslatef(0, 0, e["r"] * 0.9)
    glColor3f(0.0, 0.0, 0.0)
    glutSolidSphere(e["r"] * 0.6, 16, 16)
    glPopMatrix()

def draw_player():
    glPushMatrix()
    glTranslatef(player_pos[0], 0.0, player_z)

    # torso
    torso_height = 36
    torso_width = 26
    torso_depth = 18
    glPushMatrix()
    glColor3f(0.0, 0.6, 0.0)
    glTranslatef(0, 0, torso_height / 2.0)
    glScalef(torso_width, torso_depth, torso_height)
    glutSolidCube(1)
    glPopMatrix()

    # head
    glPushMatrix()
    glColor3f(0.0, 0.0, 0.0)
    glTranslatef(0, 0, torso_height + 12)
    glutSolidSphere(12, 20, 20)
    glPopMatrix()

    # legs
    for side in [-1, 1]:
        glPushMatrix()
        glColor3f(0.1, 0.1, 0.7)
        glTranslatef(0, side * 8, 0)
        gluCylinder(gluNewQuadric(), 5, 4, 16, 12, 1)
        glTranslatef(0, 0, 16)
        gluCylinder(gluNewQuadric(), 4, 3, 14, 12, 1)
        glPopMatrix()
    glPopMatrix()

def draw_particles():
    glBegin(GL_QUADS)
    for p in particles:
        # fade color with life
        life01 = clamp(p["life"] / 30.0, 0.0, 1.0)
        glColor3f(1.0, 0.9 * life01, 0.3 * life01)
        s = 4 + 6 * (1.0 - life01)
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
    global player_angle, cheat_mode, cheat_v_follow, player_pos, first_person

    if game_over:
        if key == b'r' or key == b'R':
            restart_game()
        return

    key = key.decode('utf-8').lower()

    # Linear path: only A/D move along X
    if key == 'a':
        player_pos[0] -= player_speed
        clamp_player_within_grid_linear()
    elif key == 'd':
        player_pos[0] += player_speed
        clamp_player_within_grid_linear()
    elif key == ' ':
        do_jump()
    elif key == 'c':
        cheat_mode = not cheat_mode
    elif key == 'v':
        first_person = not first_person
    elif key == 'r':
        restart_game()

    glutPostRedisplay()

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

    # Follow-cam that orbits slightly around Y-axis, targets player on X line
    if first_person:
        px = player_pos[0]
        # forward looks along +X
        gluLookAt(px, 0, player_z + 26, px + 100, 0, player_z + 20, 0, 0, 1)
    else:
        cx = player_pos[0] - cam_radius * math.cos(deg_to_rad(cam_theta))
        cy = cam_radius * math.sin(deg_to_rad(cam_theta)) * 0.2  # small sideways offset for depth
        cz = cam_height
        gluLookAt(cx, cy, cz, player_pos[0], 0, player_z, 0, 0, 1)

# =========================
# Game Mechanics
# =========================

def clamp_player_within_grid_linear():
    player_pos[0] = clamp(player_pos[0], -GRID_LENGTH + 40, GRID_LENGTH - 40)

def current_ground_z_at_x(x):
    # Determine the ground height directly under player's X, using platforms
    ground = 0.0
    for p in platforms:
        if p["x1"] <= x <= p["x2"]:
            ground = max(ground, p["z"])
    return ground

def do_jump():
    global player_vz, on_ground
    # Can jump only if on ground/platform
    g = current_ground_z_at_x(player_pos[0])
    if abs(player_z - (g + 40.0)) < 0.5 or on_ground:
        player_vz = jump_speed
        on_ground = False

def update_player_physics():
    global player_z, player_vz, on_ground
    # Apply gravity and move
    player_vz += gravity
    player_z += player_vz

    # Ground check
    g = current_ground_z_at_x(player_pos[0])
    min_z = g + 40.0  # player's "feet" at platform height (player base offset = 40)
    if player_z <= min_z:
        player_z = min_z
        player_vz = 0.0
        on_ground = True
    else:
        on_ground = False

def update_enemies():
    # Patrol on their platform range
    for e in enemies:
        if not e["alive"]:
            continue
        e["x"] += e["speed"]
        if e["x"] < e["x1"]:
            e["x"] = e["x1"]; e["speed"] *= -1
        if e["x"] > e["x2"]:
            e["x"] = e["x2"]; e["speed"] *= -1
        # subtle bobbing
        e["z"] += 0.2 * math.sin(e["x"] * 0.05)

def spawn_particles(x, y, z, n=10):
    for _ in range(n):
        vx = random.uniform(-1.5, 1.5)
        vy = random.uniform(-1.5, 1.5)
        vz = random.uniform(1.0, 3.2)
        particles.append({"x": x, "y": y, "z": z, "vx": vx, "vy": vy, "vz": vz, "life": 30})

def update_particles():
    alive = []
    for p in particles:
        p["x"] += p["vx"]
        p["y"] += p["vy"]
        p["z"] += p["vz"]
        p["vz"] += gravity * 0.1
        p["life"] -= 1
        if p["life"] > 0:
            alive.append(p)
    particles[:] = alive

def collect_coins():
    global coins_collected, score
    for c in coins:
        if c["taken"]:
            continue
        if abs(player_pos[0] - c["x"]) <= 20 and abs(player_z - c["z"]) <= 28:
            c["taken"] = True
            coins_collected += 1
            score += 10
            spawn_particles(c["x"], c["y"], c["z"], n=12)

def life_down(dmg=20):
    global life, game_over
    life -= dmg
    if life <= 0:
        life = 0
        game_over = True

def enemy_interactions():
    # If player lands on enemy: kill enemy (+score), bounce
    # Else if collide on same height region: take damage
    global score, player_vz
    for e in enemies:
        if not e["alive"]:
            continue
        # horizontal proximity (linear along X)
        if abs(player_pos[0] - e["x"]) <= (player_radius + e["r"]):
            # Compare heights
            dz = (player_z - 20) - (e["z"] + e["r"])  # approx feet to enemy top
            # Stomp condition: coming down (player_vz < 0) & above enemy
            if player_vz < -2.0 and dz > -6.0:
                e["alive"] = False
                e["squash"] = 0.4
                score += 50
                player_vz = jump_speed * 0.8  # bounce
                spawn_particles(e["x"], 0.0, e["z"] + e["r"], n=16)
            else:
                # If roughly at same height range => damage
                # Allow a little tolerance
                if abs(player_z - (e["z"] + e["r"])) <= 30:
                    life_down(20)
                    # small knockback
                    if player_pos[0] <= e["x"]:
                        player_pos[0] -= 20
                    else:
                        player_pos[0] += 20
                    clamp_player_within_grid_linear()

def maybe_award_extra_life():
    # 100 coins => +20 life (cap at 100)
    # This is cumulative: every 100 coins
    global coins_collected, life
    if coins_collected >= 100:
        gained = (coins_collected // 100) * 20
        life = clamp(life + gained, 0, 100)
        coins_collected = coins_collected % 100  # keep remainder

# =========================
# Idle Loop
# =========================

def idle():
    global bullet_cooldown, game_over, missed_bullets, coin_spin, day_night_t

    if bullet_cooldown > 0:
        bullet_cooldown -= 1

    if not game_over:
        update_player_physics()
        update_enemies()
        collect_coins()
        enemy_interactions()
        update_particles()
        maybe_award_extra_life()

        # spin coins
        coin_spin = (coin_spin + 4.0) % 360.0
        # day-night cycle (slow)
        day_night_t = (day_night_t + 0.002) % 1.0

    glutPostRedisplay()

# =========================
# Rendering
# =========================

def showScreen():
    # day-night tint affects clear color and a faint ambient
    dn = 0.5 + 0.5 * math.sin(day_night_t * 6.28318530718)
    sky = 0.05 + 0.20 * dn
    glClearColor(sky * 0.5, sky * 0.7, sky, 1)
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()
    glViewport(0, 0, 1000, 800)

    setupCamera()

    draw_checker_floor()
    draw_platforms()

    # Draw coins
    for c in coins:
        draw_coin(c)

    # Draw enemies
    for e in enemies:
        draw_enemy(e)

    # Draw player
    draw_player()

    # Particles last for additive feel (we're not enabling blend; just draw bright)
    draw_particles()

    # HUD
    elapsed = int(time.time() - start_time)
    draw_text(10, 770, f"Life: {life}/100")
    draw_text(10, 745, f"Score: {score}")
    draw_text(10, 720, f"Coins: {coins_collected}  (100 ⇒ +20 Life)")
    draw_text(10, 695, f"Time: {elapsed}s")
    draw_text(10, 670, f"Move: A/D   Jump: Space   View: {'First' if first_person else 'Third'} (V)   Restart: R")

    if game_over:
        draw_text(360, 400, "GAME OVER — Press R to Restart")

    glutSwapBuffers()

# =========================
# OpenGL / GLUT Setup
# =========================

def init_gl():
    glClearColor(0.05, 0.06, 0.09, 1)
    glEnable(GL_DEPTH_TEST)

def restart_game():
    global player_pos, player_angle, bullets, missed_bullets, score, life, game_over
    global cheat_mode, cheat_v_follow, first_person
    global player_z, player_vz, on_ground, start_time
    global coins_collected, particles

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
    start_time = time.time()

    gen_platforms()
    place_coins()
    init_enemies()

def main():
    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(1000, 800)
    glutInitWindowPosition(0, 0)
    glutCreateWindow("BRACU Mario — Linear 3D Platformer")

    init_gl()
    restart_game()

    glutDisplayFunc(showScreen)
    glutKeyboardFunc(keyboardListener)
    glutSpecialFunc(specialKeyListener)
    glutMouseFunc(mouseListener)
    glutIdleFunc(idle)

    glutMainLoop()

if __name__ == "__main__":
    main()
