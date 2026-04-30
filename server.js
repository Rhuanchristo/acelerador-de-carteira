const express = require('express');
const multer = require('multer');
const { exec } = require('child_process');
const path = require('path');
const fs = require('fs');
const cors = require('cors');
const os = require('os');

const app = express();
const PORT = process.env.PORT || 3001;

// Upload para pasta temporária do sistema (funciona no Render)
const upload = multer({ dest: os.tmpdir() });

app.use(cors());
app.use(express.json());

const staticDir = process.env.STATIC_DIR || __dirname;
app.use(express.static(staticDir));

// Endpoint para extrair dados do PDF
app.post('/api/extract-pdf', upload.single('pdf'), (req, res) => {
  if (!req.file) {
    return res.status(400).json({ error: 'Nenhum arquivo enviado' });
  }

  const pdfPath = req.file.path;
  // JSON de saída também na pasta temp
  const jsonPath = path.join(os.tmpdir(), `carteira-${Date.now()}.json`);

  console.log(`Processando PDF: ${req.file.originalname} -> ${pdfPath}`);

  // python3 no Linux (Render), python no Windows
  const pythonBin = process.platform === 'win32' ? 'python' : 'python3';
  const scriptPath = path.join(__dirname, 'extrair-pdf.py');
  const pythonCmd = `${pythonBin} "${scriptPath}" "${pdfPath}" "${jsonPath}"`;

  exec(pythonCmd, { cwd: __dirname }, (error, stdout, stderr) => {
    // Remove PDF temporário
    try { fs.unlinkSync(pdfPath); } catch (e) {}

    if (error) {
      console.error('Erro Python:', stderr || error.message);
      return res.status(500).json({
        error: 'Erro ao processar PDF',
        details: stderr || error.message
      });
    }

    console.log('Python output:', stdout.substring(0, 200));

    if (fs.existsSync(jsonPath)) {
      try {
        const data = JSON.parse(fs.readFileSync(jsonPath, 'utf8'));
        try { fs.unlinkSync(jsonPath); } catch (e) {}
        console.log(`Extraídos ${data.produtos.length} produtos`);
        return res.json(data);
      } catch (e) {
        return res.status(500).json({ error: 'Erro ao ler dados extraídos' });
      }
    } else {
      return res.status(500).json({ error: 'Falha ao gerar dados' });
    }
  });
});

app.listen(PORT, () => {
  console.log(`${'='.repeat(60)}`);
  console.log(`Servidor rodando na porta ${PORT}`);
  console.log(`Analisador: http://localhost:${PORT}/analisador-carteira.html`);
  console.log(`${'='.repeat(60)}`);
});
