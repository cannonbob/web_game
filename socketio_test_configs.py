"""
Socket.IO Configuration Tests
==============================

Based on your logs, the WebSocket transport upgrade is taking 48-71 seconds,
which is causing disconnects. Here are different configurations to test.

DIAGNOSIS FROM LOGS:
--------------------
- WebSocket upgrade takes 48-71 seconds (should be milliseconds)
- Disconnects happen after WebSocket upgrade attempts complete
- Clients immediately reconnect with polling transport
- Progress broadcasting is NOT the issue (no correlation with disconnects)

ROOT CAUSE: WebSocket protocol is timing out or failing on your network
"""

from flask_socketio import SocketIO

# ============================================================================
# TEST 1: Current Configuration (Default)
# ============================================================================
def config_default(app):
    """
    Current configuration - allows WebSocket upgrade
    ISSUE: WebSocket upgrade timing out
    """
    return SocketIO(app, cors_allowed_origins="*")


# ============================================================================
# TEST 2: Disable WebSocket (Recommended First Test)
# ============================================================================
def config_polling_only(app):
    """
    Force polling transport only - no WebSocket upgrade

    WHY: If WebSocket is failing, this prevents the upgrade attempt
    DOWNSIDE: Slightly higher latency, but more stable

    TO USE: In app.py, replace the socketio initialization with:
        socketio = SocketIO(app,
                           cors_allowed_origins="*",
                           transports=['polling'])
    """
    return SocketIO(app,
                   cors_allowed_origins="*",
                   transports=['polling'])


# ============================================================================
# TEST 3: Increase Timeouts
# ============================================================================
def config_increased_timeouts(app):
    """
    Allow WebSocket but increase timeouts to prevent premature disconnects

    ping_timeout: How long to wait for pong response (default 60s, now 120s)
    ping_interval: How often to send ping (default 25s)

    TO USE: In app.py:
        socketio = SocketIO(app,
                           cors_allowed_origins="*",
                           ping_timeout=120,
                           ping_interval=25)
    """
    return SocketIO(app,
                   cors_allowed_origins="*",
                   ping_timeout=120,
                   ping_interval=25)


# ============================================================================
# TEST 4: WebSocket Only (Diagnostic)
# ============================================================================
def config_websocket_only(app):
    """
    Force WebSocket only - no polling fallback

    WHY: Helps diagnose if WebSocket is completely broken
    EXPECT: If this doesn't work at all, your network blocks WebSocket

    TO USE: In app.py:
        socketio = SocketIO(app,
                           cors_allowed_origins="*",
                           transports=['websocket'])
    """
    return SocketIO(app,
                   cors_allowed_origins="*",
                   transports=['websocket'])


# ============================================================================
# TEST 5: Custom Upgrade Timeout
# ============================================================================
def config_custom_upgrade(app):
    """
    Allow WebSocket with custom upgrade timeout

    upgrade_timeout: How long to wait for WebSocket upgrade (default 10s)

    TO USE: In app.py:
        socketio = SocketIO(app,
                           cors_allowed_origins="*",
                           engineio_options={
                               'upgradeTimeout': 120000  # 120 seconds
                           })
    """
    return SocketIO(app,
                   cors_allowed_origins="*",
                   engineio_options={
                       'upgradeTimeout': 120000  # 120 seconds in milliseconds
                   })


# ============================================================================
# RECOMMENDED TEST ORDER:
# ============================================================================
"""
1. TEST 2 (polling_only) - Quick fix to see if disconnects stop
   - If disconnects stop: WebSocket is the problem
   - If disconnects continue: Different issue (maybe network quality)

2. TEST 3 (increased_timeouts) - If you want to keep WebSocket
   - Allows more time for WebSocket upgrade
   - Good middle ground

3. TEST 4 (websocket_only) - Diagnostic only
   - Only use to confirm WebSocket is completely broken
   - Don't use in production

4. TEST 5 (custom_upgrade) - Advanced
   - If WebSocket works but upgrade is slow
   - Gives more time for upgrade to complete


NOTES:
------
- The broadcast frequency (200ms) is NOT causing disconnects
- Your local network (192.168.178.x) might have WebSocket issues
- Check router/firewall settings for WebSocket protocol
- Some browsers block WebSocket to local IPs in certain configurations
"""
