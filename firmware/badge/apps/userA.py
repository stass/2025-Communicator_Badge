"""Super Star Trek - Classic game adapted for Hackaday Badge."""

import urandom as random  # type: ignore
import math

from apps.base_app import BaseApp
from ui.page import Page
import ui.styles as styles
import lvgl


class StarTrekGame:
    """Core Star Trek game logic."""
    
    GALAXY_SIZE = 8
    QUADRANT_SIZE = 8
    
    DEVICE_NAMES = [
        "", "Warp Engines", "Short Range Sensors", "Long Range Sensors",
        "Phaser Control", "Photon Tubes", "Damage Control",
        "Shield Control", "Library-Computer"
    ]
    
    # Course vectors: [dx, dy] for courses 1-8
    COURSE_VECTORS = [
        None,      # Index 0 unused
        [0, 1],    # 1 - North
        [-1, 1],   # 2 - NW
        [-1, 0],   # 3 - West
        [-1, -1],  # 4 - SW
        [0, -1],   # 5 - South
        [1, -1],   # 6 - SE
        [1, 0],    # 7 - East
        [1, 1],    # 8 - NE
    ]
    
    def __init__(self):
        self.reset_game()
    
    def reset_game(self):
        """Initialize game state."""
        # Ship status
        self.energy = 3000
        self.energy_0 = 3000
        self.shields = 0
        self.torpedoes = 10
        self.torpedoes_0 = 10
        
        # Time
        self.stardate = random.randint(2000, 4000)
        self.stardate_0 = self.stardate
        self.time_limit = random.randint(25, 35)
        
        # Position
        self.quad_x = random.randint(1, 8)
        self.quad_y = random.randint(1, 8)
        self.sect_x = random.randint(1, 8)
        self.sect_y = random.randint(1, 8)
        
        # Counts
        self.klingons_total = 0
        self.klingons_start = 0
        self.starbases_total = 0
        self.docked = False
        
        # Galaxy map [y][x] = KBBSSS format
        self.galaxy = [[0 for _ in range(8)] for _ in range(8)]
        self.known_galaxy = [[0 for _ in range(8)] for _ in range(8)]
        
        # Current quadrant
        self.quadrant_map = [[' ' for _ in range(8)] for _ in range(8)]
        self.klingons = []  # List of {x, y, energy}
        self.starbase = None  # {x, y}
        self.stars = []  # List of {x, y}
        self.k3 = 0  # Klingons in quadrant
        self.b3 = 0  # Bases in quadrant
        self.s3 = 0  # Stars in quadrant
        
        # Damage [0-8], index 0 unused
        self.damage = [0.0] * 9
        
        # Game state
        self.game_over = False
        self.game_won = False
        self.avg_klingon_energy = 200
        
        self._setup_galaxy()
        
    def _setup_galaxy(self):
        """Create the galaxy with Klingons, bases, and stars."""
        total_k = 0
        total_b = 0
        
        for y in range(8):
            for x in range(8):
                k = 0
                b = 0
                r = random.random()
                if r > 0.98:
                    k = 3
                elif r > 0.95:
                    k = 2
                elif r > 0.80:
                    k = 1
                
                if random.random() > 0.96:
                    b = 1
                
                s = random.randint(1, 8)
                self.galaxy[y][x] = k * 100 + b * 10 + s
                total_k += k
                total_b += b
        
        # Ensure at least one starbase
        if total_b == 0:
            qx = random.randint(0, 7)
            qy = random.randint(0, 7)
            if self.galaxy[qy][qx] < 200:
                self.galaxy[qy][qx] += 100
                total_k += 1
            self.galaxy[qy][qx] += 10
            total_b += 1
        
        self.klingons_total = total_k
        self.klingons_start = total_k
        self.starbases_total = total_b
        
        if self.klingons_total > self.time_limit:
            self.time_limit = self.klingons_total + 1
    
    def enter_quadrant(self, qx, qy):
        """Enter a new quadrant."""
        self.quad_x = qx
        self.quad_y = qy
        
        # Get quadrant data
        qdata = self.galaxy[qy - 1][qx - 1]
        self.known_galaxy[qy - 1][qx - 1] = qdata
        
        self.k3 = qdata // 100
        self.b3 = (qdata % 100) // 10
        self.s3 = qdata % 10
        
        # Clear map
        self.quadrant_map = [[' ' for _ in range(8)] for _ in range(8)]
        self.klingons = []
        self.starbase = None
        self.stars = []
        self.docked = False
        
        # Place Enterprise
        self.quadrant_map[self.sect_y - 1][self.sect_x - 1] = 'E'
        
        # Place Klingons
        for _ in range(self.k3):
            pos = self._find_empty_sector()
            if pos:
                x, y = pos
                energy = self.avg_klingon_energy * (0.5 + random.random())
                self.klingons.append({'x': x, 'y': y, 'energy': int(energy)})
                self.quadrant_map[y - 1][x - 1] = 'K'
        
        # Place Starbase
        if self.b3 > 0:
            pos = self._find_empty_sector()
            if pos:
                x, y = pos
                self.starbase = {'x': x, 'y': y}
                self.quadrant_map[y - 1][x - 1] = 'B'
        
        # Place Stars
        for _ in range(self.s3):
            pos = self._find_empty_sector()
            if pos:
                x, y = pos
                self.stars.append({'x': x, 'y': y})
                self.quadrant_map[y - 1][x - 1] = '*'
        
        self._check_docking()
        return self._get_quadrant_status()
    
    def _find_empty_sector(self):
        """Find a random empty sector."""
        for _ in range(100):
            x = random.randint(1, 8)
            y = random.randint(1, 8)
            if self.quadrant_map[y - 1][x - 1] == ' ':
                return (x, y)
        return None
    
    def _check_docking(self):
        """Check if docked at starbase."""
        if not self.starbase:
            return
        
        dx = abs(self.sect_x - self.starbase['x'])
        dy = abs(self.sect_y - self.starbase['y'])
        
        if dx <= 1 and dy <= 1:
            self.docked = True
            self.energy = self.energy_0
            self.torpedoes = self.torpedoes_0
            self.shields = 0
            # Repair all damage
            for i in range(1, 9):
                if self.damage[i] < 0:
                    self.damage[i] = 0
            return True
        return False
    
    def _get_quadrant_status(self):
        """Get status message for entering quadrant."""
        msgs = []
        if self.k3 > 0:
            msgs.append(f"COMBAT AREA - {self.k3} KLINGONS")
        if self.docked:
            msgs.append("DOCKED AT STARBASE")
        return msgs
    
    def get_condition(self):
        """Get ship condition."""
        if self.docked:
            return "DOCKED"
        elif self.k3 > 0:
            return "RED"
        elif self.energy < self.energy_0 * 0.1:
            return "YELLOW"
        return "GREEN"
    
    def get_time_left(self):
        """Get time remaining."""
        return self.stardate_0 + self.time_limit - self.stardate
    
    def is_device_operational(self, device_idx):
        """Check if device is operational."""
        return self.damage[device_idx] >= 0
    
    def klingon_attack(self):
        """Klingons fire at Enterprise."""
        if self.k3 <= 0 or self.docked:
            return []
        
        msgs = []
        for k in self.klingons:
            if k['energy'] <= 0:
                continue
            
            dx = k['x'] - self.sect_x
            dy = k['y'] - self.sect_y
            dist = math.sqrt(dx * dx + dy * dy)
            
            if dist == 0:
                continue
            
            hit = int((k['energy'] / dist) * (2 + random.random()))
            self.shields -= hit
            k['energy'] = int(k['energy'] / (3 + random.random()))
            
            msgs.append(f"{hit} hit from {k['x']},{k['y']}")
            
            if self.shields < 0:
                self.shields = 0
                self.game_over = True
                msgs.append("SHIELDS DOWN - DESTROYED!")
                return msgs
            
            # Damage check
            if hit >= 20 and random.random() > 0.6:
                dev = random.randint(1, 8)
                self.damage[dev] -= (hit / 200.0) + random.random() * 0.5
                msgs.append(f"{self.DEVICE_NAMES[dev]} DAMAGED")
        
        return msgs
    
    def fire_phasers(self, energy_amount):
        """Fire phasers."""
        if not self.is_device_operational(4):
            return ["PHASER CONTROL INOPERATIVE"]
        
        if self.k3 <= 0:
            return ["NO ENEMY IN QUADRANT"]
        
        if energy_amount > self.energy:
            return [f"ONLY {self.energy} AVAILABLE"]
        
        self.energy -= energy_amount
        msgs = []
        
        energy_per_k = energy_amount / self.k3
        destroyed = 0
        
        for k in self.klingons:
            if k['energy'] <= 0:
                continue
            
            dx = k['x'] - self.sect_x
            dy = k['y'] - self.sect_y
            dist = math.sqrt(dx * dx + dy * dy)
            
            if dist == 0:
                continue
            
            hit = int((energy_per_k / dist) * (2 + random.random()))
            k['energy'] -= hit
            
            if k['energy'] <= 0:
                msgs.append(f"KLINGON AT {k['x']},{k['y']} DESTROYED")
                self.quadrant_map[k['y'] - 1][k['x'] - 1] = ' '
                destroyed += 1
            else:
                msgs.append(f"{hit} hit on {k['x']},{k['y']}")
        
        self.k3 -= destroyed
        self.klingons_total -= destroyed
        
        if destroyed > 0:
            qdata = self.galaxy[self.quad_y - 1][self.quad_x - 1]
            self.galaxy[self.quad_y - 1][self.quad_x - 1] = qdata - (destroyed * 100)
        
        if self.klingons_total <= 0:
            self.game_won = True
            self.game_over = True
            msgs.append("ALL KLINGONS DESTROYED - YOU WIN!")
        
        return msgs
    
    def fire_torpedo(self, course):
        """Fire photon torpedo."""
        if self.torpedoes <= 0:
            return ["NO TORPEDOES LEFT"]
        
        if not self.is_device_operational(5):
            return ["PHOTON TUBES INOPERATIVE"]
        
        if course < 1 or course >= 9:
            return ["INVALID COURSE (1-8)"]
        
        self.torpedoes -= 1
        self.energy -= 2
        
        c_idx = int(course)
        c_frac = course - c_idx
        v1 = self.COURSE_VECTORS[c_idx]
        v2 = self.COURSE_VECTORS[c_idx + 1 if c_idx < 8 else 1]
        
        dx = v1[0] + (v2[0] - v1[0]) * c_frac
        dy = v1[1] + (v2[1] - v1[1]) * c_frac
        
        tx = float(self.sect_x)
        ty = float(self.sect_y)
        
        msgs = ["TORPEDO TRACK:"]
        
        for _ in range(20):
            tx += dx
            ty += dy
            sx = round(tx)
            sy = round(ty)
            
            if sx < 1 or sx > 8 or sy < 1 or sy > 8:
                msgs.append("MISSED")
                return msgs
            
            msgs.append(f"{sx},{sy}")
            cell = self.quadrant_map[sy - 1][sx - 1]
            
            if cell == 'K':
                msgs.append("KLINGON DESTROYED!")
                # Find and destroy the Klingon
                for k in self.klingons:
                    if k['x'] == sx and k['y'] == sy:
                        k['energy'] = 0
                        self.quadrant_map[sy - 1][sx - 1] = ' '
                        self.k3 -= 1
                        self.klingons_total -= 1
                        qdata = self.galaxy[self.quad_y - 1][self.quad_x - 1]
                        self.galaxy[self.quad_y - 1][self.quad_x - 1] = qdata - 100
                        break
                
                if self.klingons_total <= 0:
                    self.game_won = True
                    self.game_over = True
                    msgs.append("ALL KLINGONS DESTROYED!")
                return msgs
            
            elif cell == '*':
                msgs.append("STAR ABSORBS TORPEDO")
                return msgs
            
            elif cell == 'B':
                msgs.append("STARBASE DESTROYED!")
                self.starbase = None
                self.b3 = 0
                self.starbases_total -= 1
                self.quadrant_map[sy - 1][sx - 1] = ' '
                qdata = self.galaxy[self.quad_y - 1][self.quad_x - 1]
                self.galaxy[self.quad_y - 1][self.quad_x - 1] = qdata - 10
                return msgs
        
        msgs.append("MISSED")
        return msgs
    
    def set_shields(self, amount):
        """Set shield level."""
        if not self.is_device_operational(7):
            return ["SHIELD CONTROL INOPERATIVE"]
        
        total = self.energy + self.shields
        if amount > total:
            return ["INSUFFICIENT ENERGY"]
        
        self.shields = amount
        self.energy = total - amount
        return [f"SHIELDS SET TO {amount}"]
    
    def navigate(self, course, warp):
        """Navigate ship."""
        if not self.is_device_operational(1):
            if warp > 0.2:
                return ["WARP ENGINES DAMAGED - MAX 0.2"]
        
        if course < 1 or course >= 9:
            return ["INVALID COURSE (1-8)"]
        
        if warp <= 0 or warp > 8:
            return ["INVALID WARP (0.1-8)"]
        
        n = int(warp * 8)
        required = n + 10
        
        if self.energy < required:
            return [f"INSUFFICIENT ENERGY ({required} NEEDED)"]
        
        # Calculate movement
        c_idx = int(course)
        c_frac = course - c_idx
        v1 = self.COURSE_VECTORS[c_idx]
        v2 = self.COURSE_VECTORS[c_idx + 1 if c_idx < 8 else 1]
        
        dx = v1[0] + (v2[0] - v1[0]) * c_frac
        dy = v1[1] + (v2[1] - v1[1]) * c_frac
        
        # Remove Enterprise from old position
        self.quadrant_map[self.sect_y - 1][self.sect_x - 1] = ' '
        
        # Move sector by sector
        fx = float(self.sect_x)
        fy = float(self.sect_y)
        
        for i in range(1, n + 1):
            fx += dx
            fy += dy
            sx = round(fx)
            sy = round(fy)
            
            if sx < 1 or sx > 8 or sy < 1 or sy > 8:
                # Quadrant boundary - just stop for now
                sx = max(1, min(8, sx))
                sy = max(1, min(8, sy))
                self.sect_x = sx
                self.sect_y = sy
                break
            
            # Check for obstacle
            if self.quadrant_map[sy - 1][sx - 1] != ' ':
                # Back up one step
                sx = round(fx - dx)
                sy = round(fy - dy)
                self.sect_x = sx
                self.sect_y = sy
                self.quadrant_map[sy - 1][sx - 1] = 'E'
                self.energy -= n
                self.stardate += 1 if warp >= 1 else 0.1
                return ["BLOCKED BY OBSTACLE"]
            
            self.sect_x = sx
            self.sect_y = sy
        
        # Place Enterprise in new position
        self.quadrant_map[self.sect_y - 1][self.sect_x - 1] = 'E'
        
        # Consume energy and time
        self.energy -= n + 10
        self.stardate += 1 if warp >= 1 else int(warp * 10) * 0.1
        
        # Check docking
        self._check_docking()
        
        # Check time
        if self.get_time_left() <= 0:
            self.game_over = True
            return [f"TIME UP - {self.klingons_total} KLINGONS LEFT"]
        
        return [f"MOVED TO {self.sect_x},{self.sect_y}"]


class App(BaseApp):
    """Super Star Trek game app."""

    def __init__(self, name: str, badge):
        super().__init__(name, badge)
        self.foreground_sleep_ms = 50
        self.background_sleep_ms = 1000
        
        self.game = StarTrekGame()
        self.command_buffer = ""
        self.message_log = []
        self.max_messages = 12
        
        # UI elements
        self.srs_grid = []  # 8x8 grid of small rectangles
        self.status_label = None
        self.log_label = None
        self.command_label = None
        
        # Input mode
        self.input_mode = None  # None, 'course', 'warp', 'energy', 'shields', 'amount'
        self.pending_command = None
        self.input_buffer = ""

    def log(self, msg):
        """Add message to log."""
        self.message_log.append(msg)
        if len(self.message_log) > self.max_messages:
            self.message_log.pop(0)
        self.update_log_display()

    def execute_command(self, cmd):
        """Execute a game command."""
        parts = cmd.upper().split()
        if not parts:
            return
        
        command = parts[0]
        
        if command in ['NAV', 'N']:
            if len(parts) >= 3:
                try:
                    course = float(parts[1])
                    warp = float(parts[2])
                    msgs = self.game.navigate(course, warp)
                    for msg in msgs:
                        self.log(msg)
                    if not self.game.game_over:
                        attack_msgs = self.game.klingon_attack()
                        for msg in attack_msgs:
                            self.log(msg)
                    self.update_all_displays()
                except ValueError:
                    self.log("NAV <course> <warp>")
            else:
                self.log("NAV <course> <warp>")
        
        elif command in ['SRS', 'S']:
            self.update_srs_display()
            self.log("SHORT RANGE SCAN")
        
        elif command in ['LRS', 'L']:
            self.show_lrs()
        
        elif command in ['PHA', 'P']:
            if len(parts) >= 2:
                try:
                    amount = int(parts[1])
                    msgs = self.game.fire_phasers(amount)
                    for msg in msgs:
                        self.log(msg)
                    if not self.game.game_over:
                        attack_msgs = self.game.klingon_attack()
                        for msg in attack_msgs:
                            self.log(msg)
                    self.game.stardate += 0.1
                    self.update_all_displays()
                except ValueError:
                    self.log("PHA <energy>")
            else:
                self.log("PHA <energy>")
        
        elif command in ['TOR', 'T']:
            if len(parts) >= 2:
                try:
                    course = float(parts[1])
                    msgs = self.game.fire_torpedo(course)
                    for msg in msgs:
                        self.log(msg)
                    if not self.game.game_over:
                        attack_msgs = self.game.klingon_attack()
                        for msg in attack_msgs:
                            self.log(msg)
                    self.game.stardate += 0.1
                    self.update_all_displays()
                except ValueError:
                    self.log("TOR <course>")
            else:
                self.log("TOR <course>")
        
        elif command in ['SHE', 'H']:
            if len(parts) >= 2:
                try:
                    amount = int(parts[1])
                    msgs = self.game.set_shields(amount)
                    for msg in msgs:
                        self.log(msg)
                    self.update_status_display()
                except ValueError:
                    self.log("SHE <amount>")
            else:
                self.log("SHE <amount>")
        
        elif command in ['STA', 'ST']:
            self.show_status()
        
        elif command in ['DAM', 'D']:
            self.show_damage()
        
        elif command in ['HELP', '?']:
            self.log("NAV <c> <w>: Navigate")
            self.log("SRS: Short Range Scan")
            self.log("LRS: Long Range Scan")
            self.log("PHA <e>: Fire Phasers")
            self.log("TOR <c>: Fire Torpedo")
            self.log("SHE <a>: Set Shields")
            self.log("STA: Status Report")
            self.log("DAM: Damage Report")
        
        else:
            self.log(f"UNKNOWN: {command}")

    def update_srs_display(self):
        """Update short range scan display."""
        if not self.srs_grid:
            return
        
        # Color map for different objects
        colors = {
            'E': lvgl.color_hex(0x00FFFF),  # Cyan - Enterprise
            'K': lvgl.color_hex(0xFF0000),  # Red - Klingon
            'B': lvgl.color_hex(0xFF00FF),  # Magenta - Starbase
            '*': lvgl.color_hex(0xFFFF00),  # Yellow - Star
            ' ': lvgl.color_hex(0x000000),  # Black - Empty
        }
        
        # Update each cell
        for y in range(8):
            for x in range(8):
                idx = y * 8 + x
                symbol = self.game.quadrant_map[y][x]
                color = colors.get(symbol, colors[' '])
                self.srs_grid[idx].set_style_bg_color(color, 0)

    def update_status_display(self):
        """Update status display."""
        if not self.status_label:
            return
        
        g = self.game
        # Compact layout with wider column (no wrapping)
        status = f"SD:{g.stardate:.0f}\n"
        status += f"E:{g.energy}\n"
        status += f"SH:{g.shields}\n"
        status += f"T:{g.torpedoes}\n"
        status += f"K:{g.klingons_total}\n"
        status += f"TL:{g.get_time_left():.0f}\n"
        status += f"{g.get_condition()}"
        
        self.status_label.set_text(status)

    def update_log_display(self):
        """Update message log."""
        if not self.log_label:
            return
        
        # Show only 5 messages with blank line at end for command line at Y=80
        display_msgs = self.message_log[-5:]
        # Add blank line after messages to separate from command
        self.log_label.set_text("\n".join(display_msgs) + "\n")

    def update_command_display(self):
        """Update command input display."""
        if self.command_label:
            self.command_label.set_text(f">{self.command_buffer}_")

    def update_all_displays(self):
        """Update all displays."""
        self.update_srs_display()
        self.update_status_display()
        self.update_log_display()
        
        if self.game.game_over:
            if self.game.game_won:
                self.log("=== MISSION SUCCESS ===")
            else:
                self.log("=== GAME OVER ===")

    def show_status(self):
        """Show detailed status."""
        g = self.game
        self.log(f"Stardate: {g.stardate:.1f}")
        self.log(f"Condition: {g.get_condition()}")
        self.log(f"Quadrant: {g.quad_x},{g.quad_y}")
        self.log(f"Sector: {g.sect_x},{g.sect_y}")
        self.log(f"Energy: {g.energy}")
        self.log(f"Shields: {g.shields}")
        self.log(f"Torpedoes: {g.torpedoes}")
        self.log(f"Klingons: {g.klingons_total}")
        self.log(f"Time Left: {g.get_time_left():.1f}")

    def show_damage(self):
        """Show damage report."""
        self.log("DAMAGE REPORT:")
        for i in range(1, 9):
            dmg = self.game.damage[i]
            status = "OK" if dmg >= 0 else f"DMG:{dmg:.1f}"
            name = self.game.DEVICE_NAMES[i][:12]
            self.log(f"{name} {status}")

    def show_lrs(self):
        """Show long range scan."""
        g = self.game
        self.log("LONG RANGE SCAN:")
        for dy in range(-1, 2):
            line = ""
            for dx in range(-1, 2):
                qx = g.quad_x + dx
                qy = g.quad_y + dy
                if 1 <= qx <= 8 and 1 <= qy <= 8:
                    val = g.known_galaxy[qy - 1][qx - 1]
                    if val == 0 and not (dx == 0 and dy == 0):
                        line += "*** "
                    else:
                        val = g.galaxy[qy - 1][qx - 1] if (dx == 0 and dy == 0) else val
                        k = val // 100
                        b = (val % 100) // 10
                        s = val % 10
                        line += f"{k}{b}{s} "
                else:
                    line += "/// "
            self.log(line)

    def run_foreground(self):
        """Main game loop."""
        if self.game.game_over:
            # Game over - wait for reset
            if self.badge.keyboard.f1():
                self.game.reset_game()
                self.message_log = []
                msgs = self.game.enter_quadrant(self.game.quad_x, self.game.quad_y)
                for msg in msgs:
                    self.log(msg)
                self.log(f"{self.game.klingons_total} KLINGONS")
                self.log(f"{self.game.time_limit} DAYS")
                self.update_all_displays()
            elif self.badge.keyboard.f5():
                self.badge.display.clear()
                self.switch_to_background()
            return
        
        # Read keyboard input
        key = self.badge.keyboard.read_key()
        
        if key:
            if key == "\n":  # Enter
                if self.command_buffer:
                    self.execute_command(self.command_buffer)
                    self.command_buffer = ""
                    self.update_command_display()
            
            elif key == "\b":  # Backspace
                if self.command_buffer:
                    self.command_buffer = self.command_buffer[:-1]
                    self.update_command_display()
            
            elif key == "\x1b":  # Escape
                self.command_buffer = ""
                self.update_command_display()
            
            elif key.startswith("`"):  # Special keys
                pass
            
            elif key == "\t":  # Tab
                pass
            
            else:  # Regular character
                if len(self.command_buffer) < 20:
                    self.command_buffer += key
                    self.update_command_display()
        
        # F1 for help
        if self.badge.keyboard.f1():
            self.execute_command("HELP")
        
        # F5 to exit
        if self.badge.keyboard.f5():
            self.badge.display.clear()
            self.switch_to_background()

    def run_background(self):
        """Nothing to do in background."""
        super().run_background()

    def switch_to_foreground(self):
        """Setup game UI."""
        super().switch_to_foreground()
        self.p = Page()
        
        # Create info bar
        self.p.create_infobar(["USS ENTERPRISE", "NCC-1701"])
        
        # Create content area
        self.p.create_content()
        
        # 3-COLUMN LAYOUT: (Log+Cmd) | Status | SRS
        
        # LEFT COLUMN: Message log and command input
        # Message log - very short to fit command line
        self.log_label = lvgl.label(self.p.content)
        self.log_label.set_pos(2, 2)
        self.log_label.set_width(150)
        self.log_label.set_text("")
        
        # Command input - VERY HIGH UP! Position at Y=80
        self.command_label = lvgl.label(self.p.content)
        self.command_label.set_pos(2, 80)
        self.command_label.set_width(150)
        self.command_label.set_text(">_")
        
        # MIDDLE: Vertical status display
        self.status_label = lvgl.label(self.p.content)
        self.status_label.set_pos(155, 2)
        self.status_label.set_width(75)
        self.status_label.set_text("STATUS")
        
        # FAR RIGHT: Graphical SRS grid - all the way to right edge
        # 8x8 grid of 8x8 pixel squares = 64x64 total
        self.srs_grid = []
        cell_size = 8
        start_x = 295  # Push to very right edge
        start_y = 2
        
        for y in range(8):
            for x in range(8):
                cell = lvgl.obj(self.p.content)
                cell.set_size(cell_size, cell_size)
                cell.set_pos(start_x + x * cell_size, start_y + y * cell_size)
                cell.add_style(styles.base_style, 0)
                cell.set_style_bg_color(lvgl.color_hex(0x000000), 0)
                cell.set_style_border_width(0, 0)
                cell.set_style_pad_all(0, 0)
                self.srs_grid.append(cell)
        
        # Create menu bar
        self.p.create_menubar(["Help", "", "", "", "Exit"])
        self.p.replace_screen()
        
        # Initialize game
        msgs = self.game.enter_quadrant(self.game.quad_x, self.game.quad_y)
        for msg in msgs:
            self.log(msg)
        
        self.log(f"DESTROY {self.game.klingons_total} KLINGONS")
        self.log(f"{self.game.time_limit} DAYS, {self.game.starbases_total} BASES")
        self.log("F1=HELP F5=EXIT")
        
        self.update_all_displays()

    def switch_to_background(self):
        """Clean up UI."""
        self.p = None
        self.srs_grid = []
        self.status_label = None
        self.log_label = None
        self.command_label = None
        super().switch_to_background()

