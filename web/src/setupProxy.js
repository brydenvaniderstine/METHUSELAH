const path = require("path");
const fs = require("fs");

module.exports = function (app) {
  app.get("/api/gen3-bridge", (req, res) => {
    const filePath = path.resolve(__dirname, "../public/gen3_latest.json");
    try {
      const data = JSON.parse(fs.readFileSync(filePath, "utf8"));
      res.json(data);
    } catch (e) {
      res.status(404).json({ error: "gen3_latest.json not found in public/" });
    }
  });
};
