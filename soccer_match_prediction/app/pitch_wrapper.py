"""
Safe wrapper for pitch_commander to avoid circular imports and context issues
"""
import sys
import os
import traceback

# Remove this problematic block - it runs too early
# try:
#     from config.config import Config
#     sys.modules['config.config'] = sys.modules['app.config']
# except ImportError:
#     pass

def import_pitch_commander_safely():
    """Safely import pitch_commander components with proper context handling"""
    try:
        # Get project root
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)  # soccer_match_prediction folder
        
        # Clear any problematic imports
        modules_to_remove = []
        for module_name in list(sys.modules.keys()):
            if module_name and ('pitch_commander' in module_name or 'agents' in module_name):
                modules_to_remove.append(module_name)
        
        for module_name in modules_to_remove:
            try:
                del sys.modules[module_name]
            except:
                pass
        
        # Add to sys.path in correct order
        paths_to_add = []
        
        # 1. Project root (for SCORE_PULSEAIv2)
        parent_root = os.path.dirname(project_root)  # SCORE_PULSEAIv2 folder
        if parent_root not in sys.path:
            paths_to_add.append(parent_root)
        
        # 2. Project root (soccer_match_prediction)
        if project_root not in sys.path:
            paths_to_add.append(project_root)
        
        # 3. Current directory
        if current_dir not in sys.path:
            paths_to_add.append(current_dir)
        
        # Add all paths
        for path in reversed(paths_to_add):  # Add in reverse order
            sys.path.insert(0, path)
            print(f"✅ [WRAPPER] Added to sys.path: {path}")
        
        # Now import pitch_commander
        print(f"🔍 [WRAPPER] Importing pitch_commander...")
        import pitch_commander
        from pitch_commander import chatbot_bp, init_chatbot
        
        print(f"✅ [WRAPPER] Successfully imported pitch_commander")
        
        # Create a wrapped version of init_chatbot that ensures app context
        def init_chatbot_wrapped(app):
            """Wrapper that ensures pitch_commander runs in app context"""
            print(f"🔧 [WRAPPER] Initializing chatbot with app context...")
            
            # NEW: Set the config here, now that app exists
            try:
                import config  # assuming pitch_commander uses config.config
                config.config = app.config  # Set directly (better than sys.modules)
                print("✅ [WRAPPER] Set config.config to app.config")
            except ImportError as e:
                print(f"⚠️ [WRAPPER] Could not import config for patching: {e}")
            except Exception as e:
                print(f"⚠️ [WRAPPER] Config setting failed: {e}")
            
            # Store app reference in pitch_commander module for context access
            pitch_commander.current_app_instance = app
            
            # Initialize the chatbot
            try:
                init_chatbot(app)
                print(f"✅ [WRAPPER] Chatbot initialized successfully")
            except Exception as e:
                print(f"❌ [WRAPPER] Error initializing chatbot: {e}")
                traceback.print_exc()
            
            # Patch any background tasks to run in app context
            try:
                if hasattr(pitch_commander, 'ScorePulseChatbot'):
                    # Get the chatbot instance
                    chatbot_instance = getattr(pitch_commander, 'chatbot_instance', None)
                    if chatbot_instance:
                        # Patch the _update_metrics method if it exists
                        if hasattr(chatbot_instance, '_update_metrics'):
                            original_update_metrics = chatbot_instance._update_metrics
                            
                            def safe_update_metrics(*args, **kwargs):
                                with app.app_context():
                                    return original_update_metrics(*args, **kwargs)
                            
                            chatbot_instance._update_metrics = safe_update_metrics
                            print("✅ [WRAPPER] Patched _update_metrics to run in app context")
            except Exception as e:
                print(f"⚠️ [WRAPPER] Could not patch background tasks: {e}")
        
        return chatbot_bp, init_chatbot_wrapped
        
    except Exception as e:
        print(f"⚠️ [WRAPPER] Safe import of pitch_commander failed: {e}")
        traceback.print_exc()
        
        # Create dummy objects
        from flask import Blueprint
        chatbot_bp = Blueprint('chatbot', __name__)
        
        @chatbot_bp.route('/')
        def chatbot_home():
            return "Chatbot not available"
        
        def init_chatbot_dummy(app):
            print("⚠️ [WRAPPER] Dummy chatbot init - pitch_commander not available")
        
        return chatbot_bp, init_chatbot_dummy

# Export the function
__all__ = ['import_pitch_commander_safely']