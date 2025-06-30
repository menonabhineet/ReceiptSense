document.addEventListener("DOMContentLoaded", () => {

const API_ROOT   = "https://8euvwlthac.execute-api.us-east-1.amazonaws.com/prod";
const UPLOAD_URL = `${API_ROOT}/upload`;
const LIST_URL   = `${API_ROOT}/expenses`;


const $ = id => document.getElementById(id);
const fetchAllReceipts = () => fetch(LIST_URL).then(r => r.json());
let currentRows = [];


$("send").onclick = async () => {
  const file = $("file").files[0];
  if (!file){ alert("Choose a file"); return; }

  // ask backend for presigned URL
  const res = await fetch(UPLOAD_URL, { method:"POST" });
  const { presigned, key } = await res.json();

  // build a formData per S3 spec
  const fd = new FormData();
  Object.entries(presigned.fields).forEach(([k,v])=>fd.append(k,v));
  fd.append("file", file);

  // upload
  await fetch(presigned.url, { method:"POST", body: fd });
  $("up-msg").textContent = "Uploaded! It may take ~10 s to process.";
};


$("refresh").onclick = async () => {
  const vendor = $("vendor").value.trim();
  const month  = $("month").value;            // ← NEW
  const params = [];
  if (vendor) params.push(`vendor=${encodeURIComponent(vendor)}`);
  if (month)  params.push(`month=${month}`);
  const url = params.length ? `${LIST_URL}?${params.join("&")}` : LIST_URL;

  const data = await fetch(url).then(r=>r.json());
  currentRows = data;

  $("tbody").innerHTML = data
  .sort((a, b) => {
    const dateA = a.TxDate || a.Date || "";
    const dateB = b.TxDate || b.Date || "";
    return dateA.localeCompare(dateB);
  })
  .map(r => `<tr><td>${r.TxDate || r.Date}</td><td>${r.VendorNorm || r.Vendor}</td><td>${r.Category}</td><td>$${r.Total}</td><td class="del" data-id="${r.ReceiptId}">🗑️</td></tr>`)
  .join("");

};

$("dl").onclick = async ()=>{
  const url = await fetch(`${API_ROOT}/export`).then(r=>r.json()).then(j=>j.download);
  window.open(url,'_blank');
};

document.addEventListener("click", e=>{
  const btn=e.target.closest(".del");
  if(!btn) return;
  if(!confirm("Delete receipt?")) return;
  fetch(`${API_ROOT}/expenses/${btn.dataset.id}`,{method:"DELETE"})
    .then(()=>$("refresh").click());
});


let pieChartData = null;         

$("graph").onclick = async () => {

  const rows = currentRows.slice();
  if (!rows.length) { alert("No data to plot"); return; }
  

  const buckets = {};
  rows.forEach(r => {
    const cat = (r.Category || "other").toLowerCase();
    buckets[cat] = (buckets[cat] || 0) + parseFloat(r.Total);
  });
  pieChartData = buckets;         

  const labels = Object.keys(buckets);
  const values = Object.values(buckets);
  const colors = ["#3fa1ff","#ff6b3f","#ffd93f","#3fff9e",
                  "#c23fff","#ff3f9e","#7a7aff","#44d0ff"];

  const canvas = $("pie");
  if (!canvas || !canvas.getContext) {
  alert("Chart canvas not found in DOM");   
  return;
}
  const ctx     = canvas.getContext("2d");
  const w = canvas.width, h = canvas.height;
  const cx = w / 2, cy = h / 2;
  const radius = Math.min(cx, cy) - 10;
  ctx.clearRect(0, 0, w, h);


  const total = values.reduce((a, b) => a + b, 0);
  let startAngle = 0;
  values.forEach((val, i) => {
    const slice = val / total * 2 * Math.PI;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.arc(cx, cy, radius, startAngle, startAngle + slice);
    ctx.closePath();
    ctx.fillStyle = colors[i % colors.length];
    ctx.fill();
    startAngle += slice;
  });


  const lg = $("legend");
  lg.innerHTML = "";                        
  labels.forEach((lab,i)=>{
    const box = document.createElement("i");
    box.style.background = colors[i % colors.length];
    const txt = document.createTextNode(`${lab} ($${values[i].toFixed(2)})`);
    const row = document.createElement("span");
    row.append(box, txt);
    lg.append(row);
});


  $("chartModal").style.display = "flex";
};


$("closeModal").onclick = () => $("chartModal").style.display = "none";
window.addEventListener("click", e => {
  if (e.target.id === "chartModal") $("chartModal").style.display = "none";
});

$("reset").onclick = () => {
  $("vendor").value = "";
  $("month").value  = "";
  $("refresh").click();
};


$("refresh").click();

});
