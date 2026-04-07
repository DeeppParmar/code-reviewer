async function run() {
  const token = process.env.HF_TOKEN;
  if (!token) {
    throw new Error(
      "Missing HF_TOKEN env var. Set it instead of hardcoding tokens in files."
    );
  }

  if (typeof fetch !== "function") {
    throw new Error(
      "Global fetch() is not available. Use Node.js 18+ (you have it) or add a fetch polyfill."
    );
  }

  // HF Router uses model IDs like "Qwen/Qwen2.5-72B-Instruct". Some legacy
  // Inference API IDs (e.g. "mistralai/Mistral-7B-Instruct") may not exist here.
  const model = process.env.MODEL_NAME || "Qwen/Qwen2.5-72B-Instruct";
  const res = await fetch("https://router.huggingface.co/v1/chat/completions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model,
      messages: [
        { role: "system", content: "You are a helpful assistant." },
        { role: "user", content: "Explain JavaScript closures simply." },
      ],
      temperature: 0.7,
      max_tokens: 200,
    }),
  });

  const data = await res.json();
  console.log(data);
}

run();