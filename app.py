from flask import Flask, render_template, request, redirect, url_for
import psycopg2
import psycopg2.extras
import datetime

app = Flask(__name__)

# --- Conexão com o banco PostgreSQL ---
def get_db_connection():
    conn = psycopg2.connect(
        host="localhost",
        database="fleetcheck",
        user="postgres",
        password="postgres"  # troca pela tua senha real
    )
    return conn


# --- Página inicial ---
@app.route('/')
def index():
    import datetime
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '').strip()

    query = "SELECT * FROM veiculos WHERE 1=1"
    params = []

    if search:
        query += " AND (placa ILIKE %s OR motorista ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%"])

    if status_filter:
        query += " AND status = %s"
        params.append(status_filter)

    query += " ORDER BY id DESC;"
    cur.execute(query, params)
    veiculos = cur.fetchall()
    cur.close()
    conn.close()

    return render_template(
        'index.html',
        veiculos=veiculos,
        now=datetime.datetime.now,
        search=search,
        status_filter=status_filter
    )


# --- Adicionar veículo ---
@app.route('/add', methods=('GET', 'POST'))
def add_vehicle():
    if request.method == 'POST':
        placa = request.form['placa']
        motorista = request.form['motorista']
        status = request.form['status']

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO veiculos (placa, motorista, status) VALUES (%s, %s, %s)',
            (placa, motorista, status)
        )
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('index'))

    return render_template('add_vehicle.html')


# --- Editar veículo ---
@app.route('/edit/<int:id>', methods=('GET', 'POST'))
def edit_vehicle(id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT * FROM veiculos WHERE id = %s', (id,))
    veiculo = cur.fetchone()

    if request.method == 'POST':
        placa = request.form['placa']
        motorista = request.form['motorista']
        status = request.form['status']

        cur.execute(
            'UPDATE veiculos SET placa = %s, motorista = %s, status = %s WHERE id = %s',
            (placa, motorista, status, id)
        )
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('index'))

    cur.close()
    conn.close()
    return render_template('edit_vehicle.html', veiculo=veiculo)


# --- Deletar veículo ---
@app.route('/delete/<int:id>', methods=('POST',))
def delete_vehicle(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM veiculos WHERE id = %s', (id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('index'))


@app.route('/checklist', methods=['GET', 'POST'])
def checklist():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    if request.method == 'POST':
        veiculo_id = request.form.get('veiculo_id')
        observacoes = request.form.get('observacoes', '')

        # Lê os 5 radios (valores: 'aprovado' ou 'reprovado')
        bateria_val = request.form.get('bateria')
        pneu_val = request.form.get('pneu')
        eletrica_val = request.form.get('eletrica')
        motor_val = request.form.get('motor')
        qualidade_val = request.form.get('qualidade')

        if not veiculo_id:
            cur.close()
            conn.close()
            return "Erro: veículo não selecionado.", 400

        # Converte para booleanos
        def to_bool(v):
            return True if v == 'aprovado' else False

        bateria = to_bool(bateria_val)
        pneu = to_bool(pneu_val)
        eletrica = to_bool(eletrica_val)
        motor = to_bool(motor_val)
        qualidade = to_bool(qualidade_val)

        # Status final: só aprovado se TODOS forem True
        aprovado = all([bateria, pneu, eletrica, motor, qualidade])
        status_final = 'Aprovado' if aprovado else 'Reprovado'

        # Insere o checklist
        cur.execute("""
            INSERT INTO checklists
            (veiculo_id, bateria, pneu, eletrica, motor, qualidade, status, observacoes, data_check)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """, (veiculo_id, bateria, pneu, eletrica, motor, qualidade, status_final, observacoes))

        # Atualiza o veículo
        if aprovado:
            # Produção: validade +30 dias
            validade = datetime.datetime.now() + datetime.timedelta(days=30)

            # Opcional: para teste de "Expirado", definir 40 dias atrás
            # validade = datetime.datetime.now() - datetime.timedelta(days=40)

            cur.execute("""
                UPDATE veiculos
                SET status = %s,
                    validade_checklist = %s,
                    data_registro = COALESCE(data_registro, NOW())
                WHERE id = %s
            """, (status_final, validade, veiculo_id))
        else:
            # Reprovado: invalida validade
            cur.execute("""
                UPDATE veiculos
                SET status = %s,
                    validade_checklist = NULL,
                    data_registro = COALESCE(data_registro, NOW())
                WHERE id = %s
            """, (status_final, veiculo_id))

        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('index'))

    # GET -> lista veículos para o select
    cur.execute('SELECT id, placa, motorista FROM veiculos ORDER BY placa ASC;')
    veiculos = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('checklist.html', veiculos=veiculos)

