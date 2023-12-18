from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, join_room, leave_room
from flask_migrate import Migrate
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv
from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.prompts import ChatPromptTemplate
from langchain.chains import LLMChain
import os

load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
CORS(app)

app.config['SECRET_KEY'] = 'mysecretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'data.sqlite')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
Migrate(app,db)
socketio = SocketIO(app)
socketio.init_app(app, cors_allowed_origins="*")

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    chats = db.relationship('Chat', backref='user', lazy=True)

class Chat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.password == request.form['password']:
            session['username'] = user.username
            return redirect(url_for('chat'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        existing_user = User.query.filter_by(username=request.form['username']).first()
        if existing_user is None:
            new_user = User(username=request.form['username'], password=request.form['password'])
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for('login'))
        else:
            return "User already exists! Try logging in."
    return render_template('register.html')

@app.route('/chat', methods=['GET'])
def chat():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = User.query.filter_by(username=session['username']).first()
    chats = Chat.query.filter_by(user=user).all()
    return render_template('chat.html', chats=chats, username=session['username'])

@socketio.on('message')
def handle_message(data):
    user = User.query.filter_by(username=data['username']).first()
    chat = Chat(content=data['message'], user=user)
    db.session.add(chat)
    db.session.commit()

    query = data['message']
    llm = ChatOpenAI(model='gpt-3.5-turbo', temperature=0.8)
    memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
    prompt = ChatPromptTemplate.from_template(f"You are ICS Arabia chatbot so answer {query} accordingly.")

    chatbot = LLMChain(llm=llm, prompt=prompt, memory=memory)
    response = chatbot({"query": query})
    response = response['text']
    db.session.add(chat)
    db.session.commit()
    socketio.emit('message', {'user': 'Assistant', 'message': response})

if __name__ == '__main__':
    # app.run(debug=True)
    socketio.run(app)
