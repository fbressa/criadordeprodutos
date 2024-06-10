from flask import Flask, render_template, request, session, url_for, redirect
from flask_sqlalchemy import SQLAlchemy
from openai import OpenAI
import os

app = Flask(__name__)

client = OpenAI(
    api_key='sk-proj-QWedaDXnphTug5WjvONOT3BlbkFJXuQue8hJRtYyh6Gy41Ak')
app.secret_key = '123456'

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///minhabase.sqlite3'
db = SQLAlchemy(app)

UPLOAD_FOLDER = '/home/filipeb/mysite/upload'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


class Usuario(db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String)
    senha = db.Column(db.String)

    def __init__(self, nome, senha):
        self.nome = nome
        self.senha = senha


class Prod(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String, nullable=False)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)


class Produto:

    def __init__(self, descricao):
        self.descricao = descricao

    def obter_descricao(self):
        return self.descricao


class CriacDeProdutos:

    @staticmethod
    def criar_produto(descricao):
        return Produto(descricao)


class ProdutoDecorator(Produto):

    def __init__(self, produto):
        self._produto = produto

    def obter_descricao(self):
        return self._produto.obter_descricao()


class ProdutoEmDestaque(ProdutoDecorator):

    def obter_descricao(self):
        return f"Lancamento: {self._produto.obter_descricao()}"


class ProdutoComDesconto(ProdutoDecorator):

    def obter_descricao(self):
        return f"Queima de estoque: {self._produto.obter_descricao()}"


class EstrategiaDeDescricao:

    def gerar(self, descricao_base):
        raise NotImplementedError


class DescricaoSimples(EstrategiaDeDescricao):

    def gerar(self, descricao_base):
        return f"Produto simples: {descricao_base}"


class DescricaoDetalhada(EstrategiaDeDescricao):

    def gerar(self, descricao_base):
        return f"Produto detalhado com as seguintes características: {descricao_base}"


def obter_ideia_produto_inovador(prompt):
    resposta = client.chat.completions.create(
        model="gpt-3.5-turbo-0125",
        messages=[{
            'role':
                'system',
            'content':
                f'Com base na mensagem passada, crie um produto com as características passadas',
        }, {
            'role': 'user',
            'content': prompt,
        }],
        max_tokens=150,
    )
    return resposta.choices[0].message.content


# Rota de Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        nome = request.form['nome']
        senha = request.form['senha']
        if 'cadastro' in request.form:  # botão de cadastro pressionado
            usuario = Usuario(nome, senha)
            db.session.add(usuario)
            db.session.commit()
            return redirect(url_for('login_cadastro'))
        else:  # tentativa de login
            usuario = Usuario.query.filter_by(nome=nome, senha=senha).first()
            if usuario:
                session['username'] = usuario.nome
                session['password'] = usuario.senha
                return redirect(url_for('index'))
            return 'Usuario ou senha incorretos'
    return render_template('login.html')


## Rota de Cadastro
@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        nome = request.form['nome']
        senha = request.form['senha']
        if nome and senha:
            usuario = Usuario(nome, senha)
            db.session.add(usuario)
            db.session.commit()
            return redirect(url_for('login'))
    return render_template('cadastro.html')


## Rota da homepage
@app.route('/', methods=['GET', 'POST'])
def index():
    if 'username' not in session:
        return redirect(url_for('login'))

    usuario = Usuario.query.filter_by(nome=session['username']).first()
    if not usuario:
        return redirect(url_for('login'))

    if request.method == 'POST':
        prompt = request.form['prompt']
        tipo_estrategia_descricao = request.form['estrategia']
        destaque = 'destaque' in request.form
        desconto = 'desconto' in request.form

        descricao_base = obter_ideia_produto_inovador(prompt)

        if tipo_estrategia_descricao == 'detalhada':
            estrategia = DescricaoDetalhada()
        else:
            estrategia = DescricaoSimples()

        descricao_produto = estrategia.gerar(descricao_base)
        produto = CriacDeProdutos.criar_produto(descricao_produto)

        if destaque:
            produto = ProdutoEmDestaque(produto)
        if desconto:
            produto = ProdutoComDesconto(produto)

        # Armazena a descrição no banco de dados
        novo_produto = Prod(descricao=produto.obter_descricao(), id_usuario=usuario.id)
        db.session.add(novo_produto)
        db.session.commit()

        # Redirecionar para a página principal após a criação do produto
        return redirect(url_for('index'))

        # Obter lista de produtos do usuário para renderizar na página principal
    produtos = Prod.query.filter_by(id_usuario=usuario.id).all()
    return render_template('index.html', produtos=produtos)


@app.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar(id):
    if 'username' not in session:
        return redirect(url_for('login'))

    produto = Prod.query.get_or_404(id)

    if request.method == 'POST':
        produto.descricao = request.form['descricao']
        db.session.commit()
        return redirect(url_for('index'))

    return render_template('editar.html', produto=produto)


@app.route('/deletar/<int:id>', methods=['POST'])
def deletar(id):
    if 'username' not in session:
        return redirect(url_for('login'))

    produto = Prod.query.get_or_404(id)
    db.session.delete(produto)
    db.session.commit()
    return redirect(url_for('index'))


## Rota de Logout
@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)