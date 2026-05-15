# Crea la cartella che abbiamo dichiarato nel lab.conf
mkdir -p storage/web

# Crea una pagina di benvenuto semplice ma "aziendale"
cat << 'EOF' > storage/web/index.html
<!DOCTYPE html>
<html>
<head>
    <title>Cyber Corp - Home</title>
    <style>
        body { font-family: sans-serif; text-align: center; padding-top: 50px; background-color: #f4f4f4; }
        .container { border: 2px solid #333; display: inline-block; padding: 20px; background: white; }
        h1 { color: #d32f2f; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Cyber Corp Intranet</h1>
        <p>Benvenuti nel portale informativo dell'azienda.</p>
        <hr>
        <p><i>Proprietà riservata. Tutti i tentativi di accesso non autorizzati saranno loggati.</i></p>
    </div>
</body>
</html>
EOF