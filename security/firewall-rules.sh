#!/bin/bash
#
# Firewall Rules for Nabavki Platform
# UFW and iptables configuration for production security
#
# Features:
# - Allow only necessary ports
# - DDoS protection
# - Rate limiting
# - Optional geo-blocking
#

set -e

echo "=== Nabavki Platform Firewall Configuration ==="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Error: This script must be run as root"
    exit 1
fi

# Install UFW if not present
if ! command -v ufw &> /dev/null; then
    echo "Installing UFW..."
    apt-get update
    apt-get install -y ufw
fi

# Reset UFW to default state
echo "Resetting UFW to default state..."
ufw --force reset

# Default policies - deny all incoming, allow all outgoing
ufw default deny incoming
ufw default allow outgoing

# Allow SSH (change port if using non-standard)
SSH_PORT=${SSH_PORT:-22}
echo "Allowing SSH on port $SSH_PORT..."
ufw allow $SSH_PORT/tcp comment 'SSH'

# Allow HTTP and HTTPS
echo "Allowing HTTP and HTTPS..."
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'

# Rate limiting on SSH to prevent brute force
echo "Configuring SSH rate limiting..."
ufw limit $SSH_PORT/tcp

# Advanced iptables rules for DDoS protection
echo "Configuring iptables for DDoS protection..."

# Limit new connections per IP
iptables -A INPUT -p tcp --dport 80 -m state --state NEW -m recent --set
iptables -A INPUT -p tcp --dport 80 -m state --state NEW -m recent --update --seconds 10 --hitcount 20 -j DROP

iptables -A INPUT -p tcp --dport 443 -m state --state NEW -m recent --set
iptables -A INPUT -p tcp --dport 443 -m state --state NEW -m recent --update --seconds 10 --hitcount 20 -j DROP

# Limit SYN packets (SYN flood protection)
iptables -A INPUT -p tcp --syn -m limit --limit 1/s --limit-burst 3 -j ACCEPT
iptables -A INPUT -p tcp --syn -j DROP

# Protection against port scanning
iptables -N port-scanning
iptables -A port-scanning -p tcp --tcp-flags SYN,ACK,FIN,RST RST -m limit --limit 1/s --limit-burst 2 -j RETURN
iptables -A port-scanning -j DROP

# Drop invalid packets
iptables -A INPUT -m state --state INVALID -j DROP

# Drop fragmented packets
iptables -A INPUT -f -j DROP

# Drop XMAS packets
iptables -A INPUT -p tcp --tcp-flags ALL ALL -j DROP

# Drop NULL packets
iptables -A INPUT -p tcp --tcp-flags ALL NONE -j DROP

# Allow loopback
iptables -A INPUT -i lo -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT

# Allow established and related connections
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# ICMP rate limiting (allow ping but rate limit)
iptables -A INPUT -p icmp --icmp-type echo-request -m limit --limit 1/s --limit-burst 2 -j ACCEPT
iptables -A INPUT -p icmp --icmp-type echo-request -j DROP

# Optional: Geo-blocking (requires xtables-addons)
# Uncomment and configure for production use
# GEO_BLOCK_COUNTRIES="CN RU KP"
# if command -v xt_geoip &> /dev/null; then
#     echo "Configuring geo-blocking for: $GEO_BLOCK_COUNTRIES"
#     for country in $GEO_BLOCK_COUNTRIES; do
#         iptables -A INPUT -m geoip --src-cc $country -j DROP
#     done
# fi

# Save iptables rules
echo "Saving iptables rules..."
if command -v iptables-save &> /dev/null; then
    iptables-save > /etc/iptables/rules.v4
fi

# Enable UFW
echo "Enabling UFW..."
ufw --force enable

# Show status
echo ""
echo "=== Firewall Configuration Complete ==="
ufw status verbose

echo ""
echo "=== Active iptables Rules ==="
iptables -L -n -v

echo ""
echo "Firewall configuration completed successfully!"
echo ""
echo "IMPORTANT: Make sure you can still access your server via SSH before disconnecting!"
