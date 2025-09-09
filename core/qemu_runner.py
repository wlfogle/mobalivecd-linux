"""
QEMU runner for MobaLiveCD Linux
Handles QEMU execution and configuration
"""

import os
import subprocess
import shutil
import tempfile
from pathlib import Path

class QEMURunner:
    """Handles QEMU execution for ISO files"""
    
    def __init__(self):
        self.qemu_binary = self.find_qemu_binary()
        self.default_memory = "512M"
        self.default_disk_interface = "ide"
        self.use_kvm = self.check_kvm_support()
        
    def find_qemu_binary(self):
        """Find the appropriate QEMU binary"""
        candidates = [
            'qemu-system-x86_64',
            'qemu-system-i386',
            'qemu'
        ]
        
        for binary in candidates:
            if shutil.which(binary):
                return binary
                
        raise RuntimeError("QEMU not found. Please install qemu-system-x86 package")
    
    def check_kvm_support(self):
        """Check if KVM acceleration is available"""
        try:
            # Check if /dev/kvm exists and is accessible
            return os.path.exists('/dev/kvm') and os.access('/dev/kvm', os.R_OK | os.W_OK)
        except:
            return False
    
    def build_qemu_command(self, iso_path, **options):
        """Build QEMU command line arguments"""
        
        # Base command
        cmd = [self.qemu_binary]
        
        # Memory
        memory = options.get('memory', self.default_memory)
        cmd.extend(['-m', memory])
        
        # Acceleration
        if self.use_kvm and options.get('enable_kvm', True):
            cmd.extend(['-accel', 'kvm'])
        else:
            cmd.extend(['-accel', 'tcg'])
        
        # CPU - use host CPU if KVM is available
        if self.use_kvm:
            cmd.extend(['-cpu', 'host'])
        
        # Display
        display = options.get('display', 'gtk')
        if display == 'none':
            cmd.extend(['-display', 'none'])
        else:
            # Use GTK display (remove GL to avoid potential issues)
            cmd.extend(['-display', 'gtk'])
        
        # VGA
        vga = options.get('vga', 'std')
        cmd.extend(['-vga', vga])
        
        # Boot from CD-ROM
        cmd.extend(['-boot', 'd'])
        
        # Add ISO as CD-ROM
        cmd.extend(['-cdrom', iso_path])
        
        # Audio (simplified to avoid PulseAudio issues)
        if options.get('enable_audio', False):  # Disabled by default
            cmd.extend(['-audiodev', 'alsa,id=audio0'])
            cmd.extend(['-device', 'AC97,audiodev=audio0'])
        
        # USB
        cmd.extend(['-usb'])
        cmd.extend(['-device', 'usb-tablet'])  # Better mouse integration
        
        # Network (user mode)
        if options.get('enable_network', True):
            cmd.extend(['-netdev', 'user,id=net0'])
            cmd.extend(['-device', 'rtl8139,netdev=net0'])
        
        # Disable reboot on exit
        cmd.extend(['-no-reboot'])
        
        return cmd
    
    def run_iso(self, iso_path, **options):
        """Run an ISO file with QEMU"""
        if not os.path.exists(iso_path):
            raise FileNotFoundError(f"ISO file not found: {iso_path}")
        
        # Build command
        cmd = self.build_qemu_command(iso_path, **options)
        
        # Log the command for debugging
        print(f"Running: {' '.join(cmd)}")
        
        try:
            # Run QEMU - don't wait for it to complete
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE if options.get('quiet', True) else None,
                stderr=subprocess.PIPE
            )
            
            # Just check if it started successfully
            # Don't wait for completion as QEMU should run independently
            import time
            time.sleep(1)  # Give QEMU a moment to start
            
            if process.poll() is not None:
                # Process has already terminated - there was an error
                stdout, stderr = process.communicate()
                error_msg = stderr.decode('utf-8') if stderr else "QEMU failed to start"
                raise RuntimeError(f"QEMU failed: {error_msg}")
            
            print(f"QEMU started successfully with PID: {process.pid}")
                
        except FileNotFoundError:
            raise RuntimeError(f"QEMU binary '{self.qemu_binary}' not found")
        except KeyboardInterrupt:
            # User cancelled - this is normal
            pass
    
    def get_system_info(self):
        """Get system information for diagnostics"""
        info = {
            'qemu_binary': self.qemu_binary,
            'kvm_available': self.use_kvm,
            'memory': self.default_memory
        }
        
        # Get QEMU version
        try:
            result = subprocess.run(
                [self.qemu_binary, '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                info['qemu_version'] = result.stdout.strip().split('\n')[0]
        except:
            info['qemu_version'] = 'Unknown'
        
        return info
    
    def validate_iso(self, iso_path):
        """Basic validation of ISO file"""
        if not os.path.exists(iso_path):
            return False, "File does not exist"
        
        if not iso_path.lower().endswith('.iso'):
            return False, "File does not have .iso extension"
        
        # Check file size (should be > 1MB for a valid ISO)
        try:
            size = os.path.getsize(iso_path)
            if size < 1024 * 1024:  # 1MB
                return False, "File too small to be a valid ISO"
        except OSError as e:
            return False, f"Cannot read file: {e}"
        
        return True, "Valid ISO file"
