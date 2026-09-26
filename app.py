"""SPA pública +10 minutos. Execute com python app.py."""
import os
from pathlib import Path
from flask import Flask, jsonify, render_template, request
from runtime import load_bundle, estimate

ROOT = Path(__file__).resolve().parent

def create_app(artifact_dir=None):
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = 2048
    try:
        bundle = load_bundle(Path(artifact_dir or ROOT / 'artifacts'))
    except (OSError, ValueError, KeyError, TypeError, IndexError, RecursionError):
        app.logger.error('Base ou modelo ausente, inválido ou incompatível. Execute a preparação offline.')
        bundle = None

    def unavailable():
        return jsonify(error='A base ou o modelo estão indisponíveis ou incompatíveis. Tente novamente mais tarde.'), 503

    @app.get('/')
    def index():
        return render_template('index.html')

    @app.get('/api/info')
    def info():
        if bundle is None:
            return unavailable()
        return jsonify({key: bundle[key] for key in ['version', 'catalog', 'period', 'audit', 'source_url',
                        'source_sha256', 'algorithm', 'parameters', 'evaluation', 'features']})

    @app.post('/api/estimate')
    def predict():
        if bundle is None:
            return unavailable()
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or set(body) != {'day', 'time'}:
            return jsonify(error='Informe somente dia e horário válidos.'), 400
        try:
            result = estimate(bundle, body['day'], body['time'])
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        return jsonify(result)

    @app.get('/health')
    def health():
        return (jsonify(status='ready', version=bundle['version']) if bundle else unavailable())

    @app.errorhandler(413)
    def too_large(error):
        return jsonify(error='A consulta enviada é grande demais.'), 413

    @app.after_request
    def headers(response):
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Permissions-Policy'] = 'geolocation=(), camera=(), microphone=()'
        if request.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        if request.is_secure:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        return response
    return app

app = create_app()
if __name__ == '__main__':
    from waitress import serve
    serve(app, host=os.environ.get('HOST', '127.0.0.1'), port=int(os.environ.get('PORT', 8000)))
