import eventlet
eventlet.monkey_patch()

import os
import autogen
import time
import re
from flask import Flask, jsonify, request
from flask_socketio import SocketIO
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

config_list = autogen.config_list_from_json(
    "OAI_CONFIG_LIST", 
    filter_dict={
        "model": ["gpt-4o-mini"]
    }
)

class FileManager:
    def __init__(self):
        self.files = {}
        self.project_type = "nextjs"  # Default project type
        
    def save_file(self, content, file_path, task):
        """Save content to a file maintaining folder structure."""
        safe_name = re.sub(r'\W+', '_', task.lower())[:30]
        timestamp = str(int(time.time()))
        base_dir = os.path.join('generated', f"{safe_name}_{timestamp}")
        
        full_path = os.path.join(base_dir, file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        with open(full_path, 'w') as f:
            f.write(content)
            
        return full_path

    def set_project_type(self, project_type):
        """Set the project type."""
        self.project_type = project_type.lower()

    def add_file(self, file_path, content, file_type=None):
        """Add a file to the collection."""
        if file_type is None:
            extension = file_path.split('.')[-1].lower()
            file_type = self._get_file_type(extension)
        
        if file_type:
            self.files[file_path] = {
                'content': content,
                'type': file_type
            }
    
    def _get_file_type(self, extension):
        """Map file extensions to types."""
        extension_map = {
            'js': 'javascript',
            'jsx': 'javascript',
            'ts': 'javascript',
            'tsx': 'javascript',
            'css': 'css',
            'html': 'html',
            'json': 'json',
            'md': 'markdown',
            'py': 'python'
        }
        return extension_map.get(extension, 'text')

    def get_folder_structure(self):
        """Get the folder structure and file content."""
        structure = {
            'files': {},
            'content': {},
            'file_contents': {},
            'project_type': self.project_type
        }
        
        for file_path, file_data in self.files.items():
            structure['files'][file_path] = {
                'type': file_data['type'],
                'name': os.path.basename(file_path)
            }
            
            structure['content'][file_data['type']] = file_data['content']
            
            structure['file_contents'][file_path] = file_data['content']
            
        return structure

def detect_project_type(task):
    """Automatically detect the most appropriate project type based on the task description."""
    task_lower = task.lower()
    
    # Define keyword patterns for each project type
    nextjs_patterns = [
        'next.js', 'nextjs', 'server side rendering', 'ssr', 'static site generation', 'ssg',
        'next', 'vercel', 'server components', 'app router', 'pages router'
    ]
    
    react_patterns = [
        'react', 'single page application', 'spa', 'frontend', 'front-end', 'ui',
        'component', 'state management', 'hooks', 'jsx', 'tsx', 'react-dom'
    ]
    
    nodejs_patterns = [
        'node.js', 'nodejs', 'express', 'api', 'rest', 'server', 'backend', 'back-end',
        'database', 'authentication', 'authorization', 'microservice', 'mongodb', 'sql'
    ]
    
    html_patterns = [
        'html', 'css', 'vanilla javascript', 'static website', 'landing page', 'portfolio',
        'simple website', 'basic webpage', 'static site'
    ]
    
    # Count matches for each project type
    nextjs_count = sum(1 for pattern in nextjs_patterns if pattern in task_lower)
    react_count = sum(1 for pattern in react_patterns if pattern in task_lower)
    nodejs_count = sum(1 for pattern in nodejs_patterns if pattern in task_lower)
    html_count = sum(1 for pattern in html_patterns if pattern in task_lower)
    
    # Make a decision based on the highest count
    scores = {
        'nextjs': nextjs_count,
        'react': react_count,
        'nodejs': nodejs_count,
        'html': html_count
    }
    
    # If no specific patterns match, make educated guesses based on task description
    if sum(scores.values()) == 0:
        if any(word in task_lower for word in ['dashboard', 'admin', 'portal', 'commerce', 'e-commerce']):
            return 'nextjs'  # More complex applications default to Next.js
        elif any(word in task_lower for word in ['form', 'calculator', 'tool', 'widget']):
            return 'react'   # Interactive front-end tools default to React
        elif any(word in task_lower for word in ['crud', 'login', 'auth', 'data']):
            return 'nodejs'  # Data-focused applications default to Node.js
        else:
            return 'html'    # Fallback to basic HTML/CSS/JS
    
    # Return the project type with the highest score
    return max(scores, key=scores.get)

file_manager = FileManager()

class MessageHandler:
    @staticmethod
    def new_print_messages(self, message, sender, silent=False):
        """Handle new messages from agents and emit to socket."""
        if isinstance(message, dict):
            content = message.get('content', 'No content')
        else:
            content = str(message)

        # print(f"[DEBUG] Received message from {sender.name}: {content}")

        for char in content:
            socketio.emit("message", {"sender": sender.name, "content": char, "timestamp": time.strftime("%H:%M")})
            socketio.sleep(0.00005)
        socketio.sleep(0)

        if sender.name == "Developer":

            nextjs_matches = re.finditer(r'```nextjs:([^\n]+)\n(.*?)\n```', content, re.DOTALL)
            for match in nextjs_matches:
                file_path = match.group(1).strip()
                file_content = match.group(2).strip()
                file_manager.add_file(file_path, file_content, "nextjs")
            
            react_matches = re.finditer(r'```react:([^\n]+)\n(.*?)\n```', content, re.DOTALL)
            for match in react_matches:
                file_path = match.group(1).strip()
                file_content = match.group(2).strip()
                file_manager.add_file(file_path, file_content, "react")
            
            nodejs_matches = re.finditer(r'```nodejs:([^\n]+)\n(.*?)\n```', content, re.DOTALL)
            for match in nodejs_matches:
                file_path = match.group(1).strip()
                file_content = match.group(2).strip()
                file_manager.add_file(file_path, file_content, "nodejs")
            
            html_matches = re.finditer(r'```html:([^\n]+)\n(.*?)\n```', content, re.DOTALL)
            for match in html_matches:
                file_path = match.group(1).strip()
                file_content = match.group(2).strip()
                file_manager.add_file(file_path, file_content, "html")
            
            css_matches = re.finditer(r'```css:([^\n]+)\n(.*?)\n```', content, re.DOTALL)
            for match in css_matches:
                file_path = match.group(1).strip()
                file_content = match.group(2).strip()
                file_manager.add_file(file_path, file_content, "css")
            
            js_matches = re.finditer(r'```js:([^\n]+)\n(.*?)\n```', content, re.DOTALL)
            for match in js_matches:
                file_path = match.group(1).strip()
                file_content = match.group(2).strip()
                file_manager.add_file(file_path, file_content, "javascript")
            
            # Update file structure after processing
            structure = file_manager.get_folder_structure()
            socketio.emit('file_structure_update', structure)

        

autogen.GroupChatManager._print_received_message = MessageHandler.new_print_messages

developer = autogen.AssistantAgent(
    name="Developer",
    system_message="""You are a full-stack web developer expert capable of creating various web projects. Based on the project type requested, create a complete project structure with essential files.

For different project types, use the following formats:

1. Next.js applications:
```nextjs:package.json
{
  "name": "nextjs-app",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint"
  },
  "dependencies": {
    "next": "^14.0.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "eslint": "^8.40.0",
    "eslint-config-next": "^14.0.0"
  }
}```

```nextjs:next.config.js
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
}

module.exports = nextConfig```

```nextjs:assets/assetName.svg

```nextjs:pages/index.js
[Page component code]```

```nextjs:components/ComponentName.js
[Component code]```

```nextjs:styles/ComponentName.module.css
[Component styles]```

2. React applications:
   ```react:src/App.js
   [App component code]
   ```
   ```react:src/components/ComponentName.js
   [Component code]
   ```
   ```react:src/styles/ComponentName.css
   [Component styles]
   ```
   ```react:public/index.html
   [HTML template]
   ```

3. Node.js applications:
   ```nodejs:server.js
   [Server code]
   ```
   ```nodejs:routes/routeName.js
   [Route handler code]
   ```
   ```nodejs:package.json
   [Package configuration]
   ```

4. Basic HTML/CSS/JS projects:
   ```html:index.html
   [HTML code]
   ```
   ```css:styles.css
   [CSS code]
   ```
   ```js:script.js
   [JavaScript code]
   ```

Follow these guidelines:
- Use modern patterns appropriate for the framework/technology
- Implement clean, efficient code
- Include proper configuration files when needed
- Focus on writing code only - no explanations needed
- Start with essential files only""",
    llm_config={
        "cache_seed": 41,
        "config_list": config_list,
        "temperature": 0.7,
        "stream": True
    }
)

reviewer = autogen.AssistantAgent(
    name="Reviewer",
    system_message="""You are a senior code reviewer specializing in web development. Your role is to:
1. Review all generated code files
2. Check for major issues or bugs
3. Verify proper component/file structure for the specific project type
4. Ensure code follows best practices for the framework/technology
5. Keep feedback brief and focused on critical issues only
6. Approve code if it meets requirements for the specific project type""",
    llm_config={
        "cache_seed": 41,
        "config_list": config_list,
        "temperature": 0.7,
        "stream": True
    }
)

manager = autogen.AssistantAgent(
    name="Manager",
    system_message="""You are the project manager. Your role is to:
1. Understand the project requirements
2. Identify the appropriate project type (Next.js, React, Node.js, or HTML/CSS/JS) based on the requirements
3. Always explicitly state your decision about project type at the beginning: "Based on the requirements, I've determined this should be a [PROJECT TYPE] project."
4. Guide the Developer to create necessary components and files
5. Ensure all required files are generated
6. Request code review from the Reviewer
7. Keep the process moving efficiently
8. Terminate the chat when code is approved
Be concise and focused on getting results quickly.""",
    llm_config={
        "cache_seed": 41,
        "config_list": config_list,
        "temperature": 0.7,
        "stream": True
    }
)

user_proxy = autogen.UserProxyAgent(
    name="User",
    code_execution_config=False,
    human_input_mode="NEVER",
    is_termination_msg=lambda x: "TERMINATE" in str(x).upper()
)

groupchat = autogen.GroupChat(
    agents=[user_proxy, manager, developer, reviewer],
    messages=[],
    max_round=12
)

group_manager = autogen.GroupChatManager(
    groupchat=groupchat,
    llm_config={
        "cache_seed": 41,
        "config_list": config_list,
        "temperature": 0.7,
        "stream": True
    }
)

@app.route('/generate', methods=['POST'])
def generate():
    task = request.json.get('task')
    print('task: ', task)
    
    if not task:
        return jsonify({'error': 'Task is required'}), 400
    
    # Automatically detect project type from task description
    detected_project_type = detect_project_type(task)
    print('detected_project_type: ', detected_project_type)
    project_type = request.json.get('project_type', detected_project_type).lower()
    print('project_type: ', project_type)
    
    valid_project_types = ['nextjs', 'react', 'nodejs', 'html']
    if project_type not in valid_project_types:
        return jsonify({'error': f'Invalid project type. Choose from: {", ".join(valid_project_types)}'}), 400

    try:
        file_manager.files = {}
        file_manager.set_project_type(project_type)
        print('file_manager: ', file_manager)
        
        message = f"Create a {project_type.upper()} application for: {task}. Focus on essential features only."
        print('message: ', message)
        
        user_proxy.initiate_chat(
            group_manager,
            message=message
        )
        
        saved_files = {}
        for file_path, content in file_manager.files.items():
            if content:
                filepath = file_manager.save_file(content['content'], file_path, task)
                saved_files[file_path] = filepath
                socketio.emit('code_update', {
                    'type': content['type'],
                    'content': content['content']
                })
        
        folder_structure = file_manager.get_folder_structure()
        
        socketio.emit('generation_complete', {
            'files': saved_files,
            'folder_structure': folder_structure,
            'message': f'{project_type.upper()} code generation complete',
            'project_type': project_type
        })
        
        return jsonify({
            'status': 'success',
            'files': saved_files,
            'folder_structure': folder_structure,
            'project_type': project_type
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@socketio.on('connect')
def handle_connect():
    print("Client connected")
    socketio.emit("message", {"sender": "HyperTeam", "content": "Please enter your requirement"})

@socketio.on("set_project_type")
def handle_set_project_type(data):
    project_type = data.get('project_type', 'nextjs')
    file_manager.set_project_type(project_type)
    socketio.emit("message", {"sender": "HyperTeam", "content": f"Project type set to {project_type.upper()}"})

@socketio.on("disconnect")
def handle_disconnect():
    print("Client disconnected")

if __name__ == "__main__":
    socketio.run(app, debug=True, port=8080)