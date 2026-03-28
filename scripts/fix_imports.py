# fix_imports.py
import os
import sys

def read_file_with_encoding(filepath):
    """Read a file with multiple encoding attempts"""
    encodings = ['utf-8', 'latin-1', 'cp1252', 'utf-16']
    
    for encoding in encodings:
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    
    # If all encodings fail, read as binary and decode with errors ignored
    with open(filepath, 'rb') as f:
        return f.read().decode('utf-8', errors='ignore')

def write_file_with_encoding(filepath, content):
    """Write file with UTF-8 encoding"""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

def fix_models_py():
    """Add extend_existing=True to TeamNameMapping table"""
    models_path = os.path.join('app', 'models.py')
    
    try:
        content = read_file_with_encoding(models_path)
        
        # Find TeamNameMapping class and add extend_existing
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'class TeamNameMapping' in line:
                # Find the next line with __tablename__
                for j in range(i+1, min(i+10, len(lines))):
                    if '__tablename__' in lines[j]:
                        # Insert extend_existing after tablename
                        indent = lines[j].split('__tablename__')[0]
                        lines.insert(j+1, f"{indent}__table_args__ = {{'extend_existing': True}}")
                        break
                break
        
        write_file_with_encoding(models_path, '\n'.join(lines))
        print("✅ Fixed app/models.py with extend_existing=True")
    except Exception as e:
        print(f"❌ Error fixing models.py: {e}")

def fix_analyst_agent_py():
    """Fix the import in analyst_agent.py"""
    agent_path = os.path.join('agents', 'analyst_agent.py')
    
    try:
        content = read_file_with_encoding(agent_path)
        
        # Replace the problematic import with a try-except block
        old_import = "from main import MatchPredictor, TeamResolver"
        new_import = """try:
    from main import MatchPredictor, TeamResolver
except ImportError as e:
    print(f"⚠️ Could not import MatchPredictor: {e}")
    MatchPredictor = None
    TeamResolver = None"""
        
        if old_import in content:
            content = content.replace(old_import, new_import)
            write_file_with_encoding(agent_path, content)
            print("✅ Fixed agents/analyst_agent.py import")
        else:
            print("ℹ️ Import statement not found, checking for variations...")
            # Try other possible variations
            variations = [
                "from main import MatchPredictor",
                "from main import TeamResolver",
                "from ..main import",
                "from .main import"
            ]
            for var in variations:
                if var in content:
                    print(f"  Found variation: {var}")
    except Exception as e:
        print(f"❌ Error fixing analyst_agent.py: {e}")

def fix_app_init_py():
    """Fix app/__init__.py to handle imports better"""
    init_path = os.path.join('app', '__init__.py')
    
    try:
        content = read_file_with_encoding(init_path)
        
        # Find and fix the pitch_commander import section
        # Look for the try-except block with pitch_commander
        lines = content.split('\n')
        
        # First, let's find the problematic import pattern
        for i, line in enumerate(lines):
            if 'from pitch_commander import' in line and 'chatbot_bp' in line:
                # This is the line causing issues
                print(f"Found pitch_commander import at line {i+1}")
                
                # Replace with more robust import
                old_line = lines[i]
                new_line = """try:
            # First try absolute import from current directory
            from pitch_commander import chatbot_bp, init_chatbot
        except ImportError as e:
            print(f"⚠️ Pitch Commander import failed: {e}")
            # Create dummy objects to prevent crashes
            chatbot_bp = None
            def init_chatbot(app):
                print("⚠️ Chatbot initialization skipped - pitch_commander not available")
            # Register empty blueprint if needed
            if chatbot_bp:
                app.register_blueprint(chatbot_bp)"""
                
                # Replace the single line with multiple lines
                lines[i] = new_line
                
                # Also, we need to adjust the indentation for following lines
                # Find the next lines in the try block
                for j in range(i+1, min(i+20, len(lines))):
                    if 'app.register_blueprint' in lines[j] and 'chatbot_bp' in lines[j]:
                        # This line should be inside the try block
                        # Remove it since we'll handle it in the new code
                        lines[j] = ""
                        break
                
                break
        
        write_file_with_encoding(init_path, '\n'.join(lines))
        print("✅ Fixed app/__init__.py imports")
    except Exception as e:
        print(f"❌ Error fixing app/__init__.py: {e}")

def create_safe_pitch_commander_wrapper():
    """Create a safe wrapper for pitch_commander imports"""
    wrapper_content = '''"""
Safe wrapper for pitch_commander to avoid circular imports
"""
import sys
import os

def import_pitch_commander_safely():
    """Safely import pitch_commander components"""
    try:
        # Add current directory to path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
        
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        
        # Try to import
        from pitch_commander import chatbot_bp, init_chatbot
        return chatbot_bp, init_chatbot
    except Exception as e:
        print(f"⚠️ Safe import of pitch_commander failed: {e}")
        
        # Create dummy objects
        from flask import Blueprint
        chatbot_bp = Blueprint('chatbot', __name__)
        
        def init_chatbot(app):
            print("⚠️ Dummy chatbot init - pitch_commander not available")
        
        return chatbot_bp, init_chatbot

# Export the function
__all__ = ['import_pitch_commander_safely']
'''
    
    wrapper_path = os.path.join('app', 'pitch_wrapper.py')
    write_file_with_encoding(wrapper_path, wrapper_content)
    print("✅ Created safe pitch_commander wrapper")

if __name__ == '__main__':
    print("🔧 Fixing import issues with proper encoding...")
    
    # First, let's check what's actually in analyst_agent.py
    print("\n📋 Checking analyst_agent.py content...")
    agent_path = os.path.join('agents', 'analyst_agent.py')
    try:
        sample = read_file_with_encoding(agent_path)[:500]
        print("First 500 chars of analyst_agent.py:")
        print("-" * 40)
        print(sample)
        print("-" * 40)
    except Exception as e:
        print(f"❌ Could not read analyst_agent.py: {e}")
    
    # Apply fixes
    fix_models_py()
    fix_analyst_agent_py()
    fix_app_init_py()
    create_safe_pitch_commander_wrapper()
    
    print("\n✅ All fixes attempted!")
    print("\nNow update app/__init__.py to use the wrapper:")
    print("""
In app/__init__.py, replace the pitch_commander import with:

from .pitch_wrapper import import_pitch_commander_safely
chatbot_bp, init_chatbot = import_pitch_commander_safely()

if chatbot_bp:
    app.register_blueprint(chatbot_bp)
    init_chatbot(app)
""")