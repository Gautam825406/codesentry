const db = require("./db");

function searchUsers(q) {
  const sql = `SELECT * FROM users WHERE name LIKE '%${q}%'`;
  return db.query(sql);
}

module.exports = { searchUsers };
