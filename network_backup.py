##Comment only in this area
##script was generate with assitance of Claude sonnet
##



#start of code below
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Network Device Configuration Backup Script
Compatible with Python 2 and Python 3
"""

from __future__ import print_function
import os
import sys
import time
import argparse
import getpass
import datetime
import re
import socket
import paramiko
import telnetlib
import logging

# Set up logging
logging.basicConfig(
    filename='network_backup.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def get_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Network Device Configuration Backup Tool')
    parser.add_argument('-d', '--device', required=True, help='Device IP address or hostname')
    parser.add_argument('-u', '--username', required=True, help='Username for authentication')
    parser.add_argument('-p', '--password', help='Password (will prompt if not provided)')
    parser.add_argument('-e', '--enable', help='Enable password (if required)')
    parser.add_argument('-P', '--protocol', choices=['telnet', 'ssh'], default='ssh', 
                        help='Connection protocol (default: ssh)')
    parser.add_argument('-t', '--device_type', choices=['cisco_ios', 'cisco_nxos', 'juniper'], 
                        default='cisco_ios', help='Device type (default: cisco_ios)')
    parser.add_argument('-o', '--output_dir', default='./backups', 
                        help='Directory to save backups (default: ./backups)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
    
    return parser.parse_args()

def create_output_dir(directory):
    """Create the output directory if it doesn't exist."""
    if not os.path.exists(directory):
        try:
            os.makedirs(directory)
            print(f"Created directory: {directory}")
            logging.info(f"Created directory: {directory}")
        except Exception as e:
            print(f"Error creating directory {directory}: {str(e)}")
            logging.error(f"Error creating directory {directory}: {str(e)}")
            sys.exit(1)

def get_timestamp():
    """Return current timestamp in a filename-friendly format."""
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

def sanitize_hostname(hostname):
    """Convert hostname/IP to a filename-friendly format."""
    return re.sub(r'[^\w\-\.]', '_', hostname)

def telnet_backup(device, username, password, enable_password, device_type, verbose):
    """Backup device configuration using Telnet."""
    try:
        # Connect to device
        if verbose:
            print(f"Connecting to {device} via Telnet...")
        tn = telnetlib.Telnet(device, timeout=10)
        
        # Wait for username prompt
        output = tn.read_until(b"Username: ", timeout=5).decode('ascii')
        if verbose:
            print(output)
        tn.write(username.encode('ascii') + b"\n")
        
        # Wait for password prompt
        output = tn.read_until(b"Password: ", timeout=5).decode('ascii')
        if verbose:
            print(output)
        tn.write(password.encode('ascii') + b"\n")
        
        # Handle enable mode for Cisco devices
        if device_type in ['cisco_ios', 'cisco_nxos']:
            # Wait for prompt
            output = tn.read_until(b">", timeout=5).decode('ascii')
            if verbose:
                print(output)
            
            # Enter enable mode
            tn.write(b"enable\n")
            if enable_password:
                output = tn.read_until(b"Password: ", timeout=5).decode('ascii')
                if verbose:
                    print(output)
                tn.write(enable_password.encode('ascii') + b"\n")
            
            # Wait for enable prompt
            output = tn.read_until(b"#", timeout=5).decode('ascii')
            if verbose:
                print(output)
            
            # Disable pagination
            tn.write(b"terminal length 0\n")
            tn.read_until(b"#", timeout=5)
            
            # Get running config
            if device_type == 'cisco_ios':
                tn.write(b"show running-config\n")
            elif device_type == 'cisco_nxos':
                tn.write(b"show running-config | no-more\n")
        
        elif device_type == 'juniper':
            # Wait for prompt
            output = tn.read_until(b">", timeout=5).decode('ascii')
            if verbose:
                print(output)
            
            # Disable pagination and get configuration
            tn.write(b"set cli screen-length 0\n")
            tn.read_until(b">", timeout=5)
            tn.write(b"show configuration | no-more\n")
        
        # Read the configuration output
        config = b""
        while True:
            chunk = tn.read_some()
            if not chunk:
                break
            config += chunk
            # Check if we've reached the end prompt
            if b"#" in chunk or b">" in chunk:
                break
        
        # Close the connection
        tn.write(b"exit\n")
        tn.close()
        
        return config.decode('ascii', errors='ignore')
    
    except Exception as e:
        logging.error(f"Telnet error: {str(e)}")
        print(f"Error connecting via Telnet: {str(e)}")
        return None

def ssh_backup(device, username, password, enable_password, device_type, verbose):
    """Backup device configuration using SSH."""
    try:
        # Connect to device
        if verbose:
            print(f"Connecting to {device} via SSH...")
        
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client.connect(
            hostname=device,
            username=username,
            password=password,
            look_for_keys=False,
            allow_agent=False,
            timeout=10
        )
        
        # Start an interactive shell
        shell = ssh_client.invoke_shell()
        shell.settimeout(10)
        
        # Clear the initial banner
        output = shell.recv(10000).decode('ascii', errors='ignore')
        if verbose:
            print(output)
        
        # Handle enable mode for Cisco devices
        if device_type in ['cisco_ios', 'cisco_nxos']:
            # Check if we need to enter enable mode
            if '>' in output:
                shell.send("enable\n")
                time.sleep(1)
                if enable_password:
                    output = shell.recv(1000).decode('ascii', errors='ignore')
                    if 'Password' in output and verbose:
                        print(output)
                    shell.send(enable_password + "\n")
                    time.sleep(1)
            
            # Disable pagination
            shell.send("terminal length 0\n")
            time.sleep(1)
            shell.recv(1000)  # Clear the output
            
            # Get running config
            if device_type == 'cisco_ios':
                shell.send("show running-config\n")
            elif device_type == 'cisco_nxos':
                shell.send("show running-config | no-more\n")
        
        elif device_type == 'juniper':
            # Disable pagination and get configuration
            shell.send("set cli screen-length 0\n")
            time.sleep(1)
            shell.recv(1000)  # Clear the output
            shell.send("show configuration | no-more\n")
        
        # Give the device time to generate the full config
        time.sleep(5)
        
        # Read the configuration output
        config = ""
        while True:
            if shell.recv_ready():
                chunk = shell.recv(10000).decode('ascii', errors='ignore')
                config += chunk
            else:
                time.sleep(0.5)
                if not shell.recv_ready():
                    break
        
        # Close the connection
        ssh_client.close()
        
        return config
    
    except Exception as e:
        logging.error(f"SSH error: {str(e)}")
        print(f"Error connecting via SSH: {str(e)}")
        return None

def write_backup_to_file(device, config, output_dir):
    """Write the configuration to a text file."""
    if not config:
        print("No configuration data to save.")
        return False
    
    try:
        # Create the filename
        device_name = sanitize_hostname(device)
        timestamp = get_timestamp()
        filename = f"{device_name}_{timestamp}.txt"
        filepath = os.path.join(output_dir, filename)
        
        # Write the configuration to file
        with open(filepath, 'w') as f:
            f.write(config)
        
        print(f"Configuration saved to {filepath}")
        logging.info(f"Configuration saved to {filepath}")
        return True
    
    except Exception as e:
        print(f"Error writing backup file: {str(e)}")
        logging.error(f"Error writing backup file: {str(e)}")
        return False

def main():
    """Main function."""
    args = get_args()
    
    # Get password if not provided
    password = args.password
    if not password:
        password = getpass.getpass("Enter password: ")
    
    # Create the output directory
    create_output_dir(args.output_dir)
    
    # Log the start of backup
    logging.info(f"Starting backup of {args.device} using {args.protocol}")
    if args.verbose:
        print(f"Starting backup of {args.device} using {args.protocol}...")
    
    # Backup the configuration
    if args.protocol == 'telnet':
        config = telnet_backup(
            args.device, 
            args.username, 
            password, 
            args.enable, 
            args.device_type, 
            args.verbose
        )
    else:  # SSH
        config = ssh_backup(
            args.device, 
            args.username, 
            password, 
            args.enable, 
            args.device_type, 
            args.verbose
        )
    
    # Save the configuration
    success = write_backup_to_file(args.device, config, args.output_dir)
    
    # Log the result
    if success:
        logging.info(f"Backup of {args.device} completed successfully")
        if args.verbose:
            print(f"Backup of {args.device} completed successfully")
    else:
        logging.error(f"Backup of {args.device} failed")
        print(f"Backup of {args.device} failed")

if __name__ == "__main__":
    main()
