#!/usr/bin/python3
"""
This is the general script using for the deployment in the vps project
"""
import os
import sys
import subprocess
import time
import logging
from collections import deque

# Configure logging with standard library only
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger('deployment')

# Configuration
PROJECT_DIR = "/var/www/backend"
GIT_URL = "https://github.com/DeepeshKalura/creating-cd-ci-for-vps-nodejs"
NVM_DIR = os.path.expanduser("~/.nvm")
NODE_VERSION = "22"

# Queue to track deployment steps
deployment_queue = deque([
    "check_nvm_install",
    "install_node",
    "check_pm2_install",
    "ensure_pm2_config",
    "deploy_project"
])

def run_command(command, shell=False, cwd=None):
    """Run a command and return its output, handling errors"""
    try:
        if isinstance(command, str) and not shell:
            command = command.split()
        
        process = subprocess.Popen(
            command,
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd
        )
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, command, stdout, stderr)
        
        return stdout.strip()
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {' '.join(command) if isinstance(command, list) else command}")
        logger.error(f"Error: Return code {e.returncode}")
        logger.error(f"Output: {e.stdout}")
        logger.error(f"Error output: {e.stderr}")
        raise

def run_as_user(command):
    """Run a command as the current user with proper environment variables"""
    shell_command = f"bash -c 'source ~/.nvm/nvm.sh && {command}'"
    return run_command(shell_command, shell=True)

def check_nvm_install():
    """Check if NVM is installed, install if not"""
    logger.info("🔧 Checking NVM installation...")
    
    if not os.path.exists(NVM_DIR):
        logger.info("Installing NVM...")
        try:
            curl_command = f"curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.2/install.sh | bash"
            run_command(curl_command, shell=True)
            logger.info("✅ NVM installed successfully.")
        except Exception as e:
            logger.error(f"Failed to install NVM: {e}")
            raise
    else:
        logger.info("✅ NVM already installed.")
    
    # Verify NVM is working
    try:
        run_as_user("nvm --version")
        logger.info("✅ NVM is properly configured.")
    except Exception:
        logger.error("NVM is installed but not configured properly in bashrc.")
        logger.info("Adding NVM configuration to bashrc...")
        with open(os.path.expanduser("~/.bashrc"), "a") as f:
            f.write('\n# NVM Configuration\n')
            f.write('export NVM_DIR="$HOME/.nvm"\n')
            f.write('[ -s "$NVM_DIR/nvm.sh" ] && \\. "$NVM_DIR/nvm.sh"\n')
            f.write('[ -s "$NVM_DIR/bash_completion" ] && \\. "$NVM_DIR/bash_completion"\n')
        logger.info("✅ NVM configuration added to .bashrc")
        # Source the updated .bashrc
        run_command("source ~/.bashrc", shell=True)

def install_node():
    """Install and use the specified Node.js version"""
    logger.info(f"🔧 Installing Node.js v{NODE_VERSION}...")
    
    try:
        # Install Node.js
        run_as_user(f"nvm install {NODE_VERSION}")
        run_as_user(f"nvm use {NODE_VERSION}")
        
        # Verify installation
        node_version = run_as_user("node -v")
        npm_version = run_as_user("npm -v")
        
        logger.info(f"✅ Node version: {node_version}")
        logger.info(f"✅ NPM version: {npm_version}")
    except Exception as e:
        logger.error(f"Failed to install Node.js: {e}")
        raise

def check_pm2_install():
    """Check if PM2 is installed, install if not"""
    logger.info("🔍 Checking PM2...")
    
    try:
        # Check if PM2 is installed
        pm2_version = run_as_user("pm2 -v")
        logger.info(f"✅ PM2 is already installed: {pm2_version}")
    except Exception:
        logger.info("🛠️ PM2 not found. Installing...")
        try:
            run_as_user("npm install -g pm2")
            pm2_version = run_as_user("pm2 -v")
            logger.info(f"✅ PM2 installed successfully: {pm2_version}")
        except Exception as e:
            logger.error(f"Failed to install PM2: {e}")
            raise

def ensure_pm2_config():
    """Ensure PM2 is properly configured in bashrc"""
    logger.info("🔧 Checking PM2 configuration...")
    
    bashrc_path = os.path.expanduser("~/.bashrc")
    
    # Check if PM2 path is in .bashrc
    pm2_config_exists = False
    try:
        with open(bashrc_path, 'r') as f:
            bashrc_content = f.read()
        pm2_config_exists = "PM2_HOME" in bashrc_content or "pm2" in bashrc_content
    except:
        # If file doesn't exist or can't be read, assume no config
        pm2_config_exists = False
    
    if not pm2_config_exists:
        logger.info("Adding PM2 configuration to .bashrc...")
        try:
            with open(bashrc_path, 'a') as f:
                f.write('\n# PM2 Configuration\n')
                f.write('export PM2_HOME="$HOME/.pm2"\n')
                f.write('export PATH="$PATH:$HOME/node_modules/.bin"\n')
            
            # Setup PM2 startup
            try:
                run_as_user("pm2 startup")
                logger.info("✅ PM2 configured to start on boot")
            except Exception as e:
                logger.warning(f"Could not setup PM2 startup: {e}")
        except Exception as e:
            logger.error(f"Failed to update bashrc: {e}")
            raise
    else:
        logger.info("✅ PM2 already configured in .bashrc")

def deploy_project():
    """Deploy or update the project"""
    logger.info("📁 Checking if project exists...")
    
    project_git_dir = os.path.join(PROJECT_DIR, ".git")
    
    if os.path.exists(project_git_dir):
        # Update existing project
        logger.info("📥 Project exists, pulling latest...")
        try:
            run_command("git pull origin main", cwd=PROJECT_DIR)
            
            # Fix permissions
            logger.info("🧹 Fixing permissions...")
            username = os.environ.get('USER', os.environ.get('USERNAME'))
            run_command(f"sudo chown -R {username}:{username} {PROJECT_DIR}", shell=True)
            
            # Install dependencies
            logger.info("📦 Installing dependencies...")
            run_as_user(f"cd {PROJECT_DIR} && npm install --omit=dev")
            
            # Restart with PM2
            logger.info("♻️ Restarting with PM2...")
            try:
                run_as_user(f"pm2 restart backend")
                logger.info("✅ Application restarted successfully")
            except Exception:
                logger.info("Application not yet in PM2, starting fresh...")
                run_as_user(f"pm2 start index.js --name backend --cwd {PROJECT_DIR}")
        except Exception as e:
            logger.error(f"Failed to update project: {e}")
            raise
    else:
        # Fresh clone
        logger.info("📦 Project not found, cloning fresh...")
        try:
            # Remove existing directory if it exists
            if os.path.exists(PROJECT_DIR):
                run_command(f"sudo rm -rf {PROJECT_DIR}", shell=True)
            
            # Clone the repository
            run_command(f"sudo git clone {GIT_URL} {PROJECT_DIR}", shell=True)
            
            # Fix permissions
            logger.info("🧹 Fixing permissions...")
            username = os.environ.get('USER', os.environ.get('USERNAME'))
            run_command(f"sudo chown -R {username}:{username} {PROJECT_DIR}", shell=True)
            
            # Install dependencies
            logger.info("📦 Installing dependencies...")
            run_as_user(f"cd {PROJECT_DIR} && npm install --omit=dev")
            
            # Start with PM2
            logger.info("🚀 Starting with PM2...")
            run_as_user(f"pm2 start index.js --name backend --cwd {PROJECT_DIR}")
        except Exception as e:
            logger.error(f"Failed to clone project: {e}")
            raise

def main():
    """Main function to execute deployment steps"""
    logger.info("🚀 Starting deployment process...")
    
    # Process each step in the queue
    while deployment_queue:
        current_step = deployment_queue.popleft()
        
        try:
            logger.info(f"Executing step: {current_step}")
            globals()[current_step]()
        except Exception as e:
            logger.error(f"Step {current_step} failed: {e}")
            # Put the failed step back in the queue
            deployment_queue.appendleft(current_step)
            logger.info(f"Will retry {current_step} in 5 seconds...")
            time.sleep(5)
            continue
    
    logger.info("🎉 Deployment complete.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Deployment interrupted by user.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        sys.exit(1)