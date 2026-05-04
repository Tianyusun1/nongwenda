const chatWindow = document.getElementById('chatWindow');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');

const esc = (s='') => String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function append(role, text){ const div=document.createElement('div'); div.className=role; div.innerHTML=esc(text).replace(/\n/g,'<br>'); chatWindow.appendChild(div);}

sendBtn.onclick = async () => {
  const msg = userInput.value.trim(); if(!msg) return;
  append('u', msg); userInput.value='';
  const res = await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'include',body:JSON.stringify({message:msg})});
  const data = await res.json();
  append('b', data.reply || data.msg || '系统繁忙');
};

async function loadProducts(){
  const q = document.getElementById('q').value.trim();
  const res = await fetch(`/api/products?q=${encodeURIComponent(q)}`,{credentials:'include'});
  const data = await res.json();
  document.getElementById('products').innerHTML = (data.data||[]).map(i=>`<li>${esc(i.name)} / ¥${i.price} / 库存${i.stock}</li>`).join('');
}
window.loadProducts = loadProducts;

async function loadOrders(){
  const res = await fetch('/api/orders',{credentials:'include'});
  const data = await res.json();
  document.getElementById('orders').innerHTML = (data.data||[]).map(i=>`<li>${esc(i.order_no)} - ${esc(i.status)} - ¥${i.total_amount}</li>`).join('');
}
window.loadOrders = loadOrders;
