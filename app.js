// app.js
const express = require("express");
const app = express();

app.get("/", (_, res) => {
  res.send("Namaste World!");
});

module.exports = app;
