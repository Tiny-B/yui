# // npx node@4 proxy.js <-- runs file

# import express from 'express';
# import cors from 'cors';
# import bodyParser from 'body-parser';
# import { Ollama } from 'ollama';

# const app = express();
# const port = 3001; // any port

# app.use(cors()); // enable CORS for front‑end
# app.use(bodyParser.json());

# // Ollama client – ONLY on the server side
# const ollama = new Ollama({
# 	host: 'http://127.0.0.1:11434',
# });

# // API endpoint that forwards the request
# app.post('/api/generate', async (req, res) => {
# 	const { model, prompt, stream, temperature, keep_alive } = req.body;

# 	try {
# 		// If need streaming can expose it as SSE
# 		const result = await ollama.generate({
# 			model,
# 			prompt,
# 			stream: !!stream,
# 			temperature,
# 			keep_alive,
# 		});
# 		res.json(result);
# 	} catch (err) {
# 		console.error('Ollama error', err);
# 		res.status(500).json({ error: err.message || 'Ollama failure' });
# 	}
# });

# app.listen(port, () => {
# 	console.log(`Ollama proxy listening on http://localhost:${port}`);
# });
