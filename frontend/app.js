const API = window.location.port === "8000" || window.location.hostname !== "localhost"
  ? window.location.origin
  : "http://localhost:8000";


(function detectNgrok(){
  if(API.includes("ngrok")){
    document.getElementById("ngrok-banner").style.display="flex";
    document.getElementById("ngrok-url-display").textContent=API;
  }
})();

let userId  = localStorage.getItem("zf_id")     || "";
let perfil  = localStorage.getItem("zf_perfil") || "";
let nomeUser= localStorage.getItem("zf_nome")   || "";
let cardapio= [];
let carrinho= {};
let catAtual= "Todos";
let meusPedidosCache = "";
let cozinhaCache = "";

const STATUS_STEPS = ["recebido","confirmado","preparando","pronto","entregando","entregue"];
const STATUS_LABELS= {
  recebido:"Recebido",confirmado:"Confirmado",preparando:"Preparando",
  pronto:"Pronto",entregando:"Saiu para entrega",entregue:"Entregue",cancelado:"Cancelado"
};

const fmt = v => "R$ " + parseFloat(v).toFixed(2).replace(".",",");

function toast(msg, tipo="ok"){
  const el=document.getElementById("toast");
  el.textContent=msg; el.className="toast show"+(tipo==="err"?" err":"");
  setTimeout(()=>el.classList.remove("show"),3500);
}

function setErro(id,msg){
  const i=document.getElementById(id), e=document.getElementById("err-"+id);
  if(i)i.classList.add("error");
  if(e){e.textContent=msg;e.classList.add("show");}
}
function limparErro(id){
  const i=document.getElementById(id), e=document.getElementById("err-"+id);
  if(i)i.classList.remove("error");
  if(e)e.classList.remove("show");
}

function userHeaders(extra={}){
  return {
    ...extra,
    "X-User-Id": userId || "1",
    "X-User-Perfil": perfil || "cliente",
    "X-User-Nome": nomeUser || "Usuario Teste",
  };
}

function switchAuthTab(tab){
  document.getElementById("form-login").style.display    = tab==="login"    ?"block":"none";
  document.getElementById("form-cadastro").style.display = tab==="cadastro" ?"block":"none";
  document.getElementById("tab-login").classList.toggle("active",    tab==="login");
  document.getElementById("tab-cadastro").classList.toggle("active", tab==="cadastro");
}

const validEmail = v => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);

function validarLogin(){
  let ok=true;
  const email=document.getElementById("l-email").value.trim();
  const senha=document.getElementById("l-senha").value;
  if(!email||!validEmail(email)){setErro("l-email","E-mail inválido");ok=false;}
  if(!senha){setErro("l-senha","Informe a senha");ok=false;}
  return ok;
}

function validarCadastro(){
  let ok=true;
  const nome  =document.getElementById("c-nome").value.trim();
  const email =document.getElementById("c-email").value.trim();
  const senha =document.getElementById("c-senha").value;
  const senha2=document.getElementById("c-senha2").value;
  if(nome.length<3){setErro("c-nome","Mínimo 3 caracteres");ok=false;}
  if(!validEmail(email)){setErro("c-email","E-mail inválido");ok=false;}
  if(senha.length<6){setErro("c-senha","Mínimo 6 caracteres");ok=false;}
  if(senha!==senha2){setErro("c-senha2","As senhas não coincidem");ok=false;}
  return ok;
}

async function fazerLogin(){
  if(!validarLogin()) return;
  const btn=document.getElementById("btn-login");
  btn.disabled=true; btn.textContent="Entrando...";
  try{
    const res=await fetch(`${API}/auth/login`,{
      method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({email:document.getElementById("l-email").value.trim(), senha:document.getElementById("l-senha").value})
    });
    const data=await res.json();
    if(res.ok){salvarSessao(data);iniciarApp();}
    else toast(data.detail||"E-mail ou senha incorretos","err");
  }catch{toast("Não foi possível conectar à API. Verifique se o servidor está rodando.","err");}
  btn.disabled=false; btn.textContent="Entrar";
}

async function fazerCadastro(){
  if(!validarCadastro()) return;
  const btn=document.getElementById("btn-cadastro");
  btn.disabled=true; btn.textContent="Criando conta...";
  try{
    const res=await fetch(`${API}/auth/cadastro`,{
      method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({nome:document.getElementById("c-nome").value.trim(), email:document.getElementById("c-email").value.trim(), senha:document.getElementById("c-senha").value})
    });
    const data=await res.json();
    if(res.ok){salvarSessao(data);iniciarApp();}
    else toast(data.detail||"Erro no cadastro","err");
  }catch{toast("Não foi possível conectar à API.","err");}
  btn.disabled=false; btn.textContent="Criar conta";
}

function salvarSessao(d){
  userId=String(d.id || "1"); perfil=d.perfil; nomeUser=d.nome;
  localStorage.setItem("zf_id",userId);
  localStorage.setItem("zf_perfil",perfil);
  localStorage.setItem("zf_nome",nomeUser);
}

function logout(){
  userId=perfil=nomeUser=""; carrinho={};
  meusPedidosCache = "";
  cozinhaCache = "";
  ["zf_id","zf_token","zf_perfil","zf_nome"].forEach(k=>localStorage.removeItem(k));
  document.getElementById("auth-screen").style.display="flex";
  document.getElementById("app-screen").style.display="none";
}

function iniciarApp(){
  document.getElementById("auth-screen").style.display="none";
  document.getElementById("app-screen").style.display="block";
  document.getElementById("user-badge").textContent=nomeUser+(perfil==="cozinha"?" 👨‍🍳":"");
  const nav=document.getElementById("app-nav");
  if(perfil==="cliente"){
    nav.innerHTML=`
      <button class="nav-btn active" onclick="showPage('cardapio',this)">🍽 Cardápio</button>
      <button class="nav-btn"        onclick="showPage('pedidos',this)">📋 Meus Pedidos</button>`;
    showPage("cardapio",nav.children[0]);
    carregarCardapio();
  } else {
    nav.innerHTML=`<button class="nav-btn active" onclick="showPage('cozinha',this)">👨‍🍳 Painel da Cozinha</button>`;
    showPage("cozinha",nav.children[0]);
    carregarCozinha();
  }
}

function showPage(nome,btn){
  document.querySelectorAll(".page").forEach(p=>p.classList.remove("active"));
  document.querySelectorAll(".nav-btn").forEach(b=>b.classList.remove("active"));
  document.getElementById("page-"+nome).classList.add("active");
  btn.classList.add("active");
  if(nome==="pedidos") carregarMeusPedidos();
  if(nome==="cozinha") carregarCozinha();
}

function abrirDrawer(){
  document.getElementById("cart-overlay").classList.add("open");
  document.getElementById("cart-drawer").classList.add("open");
  document.body.style.overflow="hidden";
}
function fecharDrawer(){
  document.getElementById("cart-overlay").classList.remove("open");
  document.getElementById("cart-drawer").classList.remove("open");
  document.body.style.overflow="";
}

async function carregarCardapio(){
  try{
    const res=await fetch(`${API}/cardapio`,{headers:userHeaders()});
    const data=await res.json();
    cardapio=data.itens;
    const badge=document.getElementById("cache-badge");
    if(data.fonte==="redis_cache"){
      badge.textContent=`⚡ Redis · TTL ${data.ttl}s`;
      Object.assign(badge.style,{background:"#d1fae5",color:"#2d7a4f"});
    } else {
      badge.textContent="📦 Cache recarregado";
      Object.assign(badge.style,{background:"#fef3c7",color:"#b07d1a"});
    }
    renderMenu();
  }catch{
    document.getElementById("menu-grid").innerHTML=`<p style="color:var(--danger)">⚠ API offline. Verifique o servidor.</p>`;
  }
}

function renderMenu(){
  const itens=catAtual==="Todos"?cardapio:cardapio.filter(i=>i.categoria===catAtual);
  document.getElementById("menu-grid").innerHTML=itens.map(item=>`
    <div class="menu-card" onclick="addItem(${item.id})">
      <span class="menu-emoji">${item.emoji}</span>
      <div class="menu-name">${item.nome}</div>
      <div class="menu-desc">${item.descricao}</div>
      <div class="menu-footer">
        <span class="menu-price">${fmt(item.preco)}</span>
        <button class="add-btn" onclick="event.stopPropagation();addItem(${item.id})">+</button>
      </div>
    </div>`).join("");
}

function filtrar(cat,btn){
  catAtual=cat;
  document.querySelectorAll(".cat-btn").forEach(b=>b.classList.remove("active"));
  btn.classList.add("active"); renderMenu();
}

function addItem(id){
  const item=cardapio.find(i=>i.id===id); if(!item) return;
  carrinho[id]?carrinho[id].quantidade++:(carrinho[id]={...item,quantidade:1});
  renderCarrinho();
  toast(`${item.emoji} ${item.nome} adicionado!`);
}
function alterarQtd(id,d){
  if(!carrinho[id]) return;
  carrinho[id].quantidade+=d;
  if(carrinho[id].quantidade<=0) delete carrinho[id];
  renderCarrinho();
}

function renderCarrinho(){
  const itens=Object.values(carrinho);
  const count=itens.reduce((s,i)=>s+i.quantidade,0);
  const total=itens.reduce((s,i)=>s+i.preco*i.quantidade,0);

  ["cart-count","cart-count-d"].forEach(id=>{const e=document.getElementById(id);if(e)e.textContent=count;});
  document.getElementById("fab-count").textContent=count;

  const html=itens.length===0
    ?`<div class="cart-empty">Adicione itens ao carrinho!</div>`
    :itens.map(i=>`
      <div class="cart-item">
        <span class="ci-emoji">${i.emoji}</span>
        <div class="ci-info">
          <div class="ci-name">${i.nome}</div>
          <div class="ci-price">${fmt(i.preco*i.quantidade)}</div>
        </div>
        <div class="ci-qty">
          <button class="qty-btn" onclick="alterarQtd(${i.id},-1)">−</button>
          <span class="qty-n">${i.quantidade}</span>
          <button class="qty-btn" onclick="alterarQtd(${i.id},+1)">+</button>
        </div>
      </div>`).join("");

  ["cart-items","cart-items-d"].forEach(id=>{const e=document.getElementById(id);if(e)e.innerHTML=html;});
  const show=itens.length>0,d=show?"block":"none";
  ["cart-total-box","cart-total-box-d","cart-form-box","cart-form-box-d"].forEach(id=>{
    const e=document.getElementById(id);if(e)e.style.display=d;
  });
  if(show){
    ["ct-sub","ct-sub-d"].forEach(id=>{const e=document.getElementById(id);if(e)e.textContent=fmt(total);});
    ["ct-tot","ct-tot-d"].forEach(id=>{const e=document.getElementById(id);if(e)e.textContent=fmt(total);});
  }
  const txt=show?`Fazer Pedido · ${fmt(total)}`:"Adicione itens para pedir";
  ["btn-pedido","btn-pedido-d"].forEach(id=>{const b=document.getElementById(id);if(b){b.disabled=!show;b.textContent=txt;}});
}

async function fazerPedido(orig){
  const endId=orig==="mob"?"input-end-d":"input-end";
  const end=document.getElementById(endId).value.trim();
  if(end.length<10){setErro(endId,"Endereço muito curto (mín. 10 caracteres)");return;}
  if(end.length>200){setErro(endId,"Endereço muito longo (máx. 200 caracteres)");return;}

  const itens=Object.values(carrinho).map(i=>({produto_id:i.id,quantidade:i.quantidade}));
  const btnId=orig==="mob"?"btn-pedido-d":"btn-pedido";
  const btn=document.getElementById(btnId);
  btn.disabled=true; btn.textContent="Enviando...";
  try{
    const res=await fetch(`${API}/pedidos`,{
      method:"POST",
      headers:userHeaders({"Content-Type":"application/json"}),
      body:JSON.stringify({endereco:end,itens}),
    });
    const data=await res.json();
    if(res.ok){
      toast(`✅ Pedido #${data.pedido_id.slice(0,8)} criado! ${fmt(data.total)}`);
      carrinho={};
      ["input-end","input-end-d"].forEach(id=>{const e=document.getElementById(id);if(e)e.value="";});
      renderCarrinho(); fecharDrawer();
    } else {
      const msg=data.detail;
      if(Array.isArray(msg)) msg.forEach(e=>toast(e.msg||JSON.stringify(e),"err"));
      else toast(msg||"Erro ao criar pedido","err");
    }
  }catch{toast("Erro de conexão com a API","err");}
  btn.disabled=false;
}

async function carregarMeusPedidos(){
  try{
    const res=await fetch(`${API}/pedidos/meus`,{headers:userHeaders()});
    const data=await res.json();
    const novoCache = JSON.stringify(data.pedidos || []);
    if(novoCache === meusPedidosCache) return;
    meusPedidosCache = novoCache;
    const lista=document.getElementById("meus-pedidos-list");
    lista.innerHTML=data.pedidos.length===0
      ?`<p style="color:var(--muted);font-size:.87rem">Nenhum pedido ainda. Faça seu primeiro pedido!</p>`
      :data.pedidos.map(p=>renderPedidoCliente(p)).join("");
  }catch{
    document.getElementById("meus-pedidos-list").innerHTML=`<p style="color:var(--danger)">⚠ Erro ao carregar pedidos.</p>`;
  }
}

function progressBar(status){
  const idx=STATUS_STEPS.indexOf(status);
  return STATUS_STEPS.map((s,i)=>`<div class="progress-step ${i<idx?"done":i===idx?"active":""}"></div>`).join("");
}

function renderPedidoCliente(p){
  const cancelavel=["recebido","confirmado"].includes(p.status);
  return `
    <div class="pedido-card">
      <div class="pedido-top">
        <div class="pedido-info"><h3>${p.endereco}</h3><p>Feito às ${p.criado_em}</p></div>
        <div class="pedido-right">
          <span class="status-badge s-${p.status}">${STATUS_LABELS[p.status]||p.status}</span>
          <span class="pedido-id">#${p.id.slice(0,8)}</span>
        </div>
      </div>
      ${p.status!=="cancelado"?`<div class="progress-track">${progressBar(p.status)}</div>`:""}
      <div class="pedido-itens">${p.itens.map(i=>`<span class="pit">${i.emoji} ${i.nome} ×${i.quantidade}</span>`).join("")}</div>
      <div class="pedido-bottom">
        <span class="pedido-total">${fmt(p.total)}</span>
        <span class="pedido-time">atualizado ${p.atualizado_em}</span>
        ${cancelavel?`<button class="btn-cancel" onclick="cancelarPedido('${p.id}')">Cancelar</button>`:""}
      </div>
    </div>`;
}

async function cancelarPedido(id){
  if(!confirm("Cancelar este pedido?")) return;
  try{
    const res=await fetch(`${API}/pedidos/${id}`,{method:"DELETE",headers:userHeaders()});
    const data=await res.json();
    res.ok?(toast("Pedido cancelado."),carregarMeusPedidos()):toast(data.detail,"err");
  }catch{toast("Erro ao cancelar","err");}
}

async function carregarCozinha(){
  try{
    const [pRes,fRes]=await Promise.all([
      fetch(`${API}/cozinha/pedidos`,{headers:userHeaders()}),
      fetch(`${API}/cozinha/fila`,   {headers:userHeaders()}),
    ]);
    const pData=await pRes.json(), fData=await fRes.json();
    document.getElementById("fila-msgs").textContent=fData.mensagens_pendentes??"—";

    const pedidos=pData.pedidos||[];
    const novoCache = JSON.stringify({pedidos, fila:fData.mensagens_pendentes??"—"});
    if(novoCache === cozinhaCache) return;
    cozinhaCache = novoCache;
    const emPreparo=pedidos.filter(p=>["confirmado","preparando","pronto","entregando"].includes(p.status)).length;
    const entregues=pedidos.filter(p=>p.status==="entregue").length;
    const receita  =pedidos.filter(p=>p.status!=="cancelado").reduce((s,p)=>s+p.total,0);
    document.getElementById("st-total").textContent=pedidos.length;
    document.getElementById("st-prep").textContent =emPreparo;
    document.getElementById("st-ent").textContent  =entregues;
    document.getElementById("st-rec").textContent  =fmt(receita);

    const lista=document.getElementById("cozinha-list");
    lista.innerHTML=pedidos.length===0
      ?`<p style="color:var(--muted);font-size:.87rem">Nenhum pedido ainda.</p>`
      :pedidos.map(p=>renderPedidoCozinha(p)).join("");
  }catch{
    document.getElementById("cozinha-list").innerHTML=`<p style="color:var(--danger)">⚠ Erro ao carregar.</p>`;
  }
}

const STATUS_OPTIONS=["recebido","confirmado","preparando","pronto","entregando","entregue","cancelado"];

function renderPedidoCozinha(p){
  const opts=STATUS_OPTIONS.map(s=>`<option value="${s}" ${s===p.status?"selected":""}>${STATUS_LABELS[s]||s}</option>`).join("");
  return `
    <div class="pedido-card">
      <div class="pedido-top">
        <div class="pedido-info"><h3>${p.cliente_nome}</h3><p>${p.endereco} · ${p.criado_em}</p></div>
        <div class="pedido-right">
          <span class="status-badge s-${p.status}">${STATUS_LABELS[p.status]||p.status}</span>
          <span class="pedido-id">#${p.id.slice(0,8)}</span>
        </div>
      </div>
      ${p.status!=="cancelado"?`<div class="progress-track">${progressBar(p.status)}</div>`:""}
      <div class="pedido-itens">${p.itens.map(i=>`<span class="pit">${i.emoji} ${i.nome} ×${i.quantidade}</span>`).join("")}</div>
      <div class="pedido-bottom">
        <span class="pedido-total">${fmt(p.total)}</span>
        <span class="pedido-time">atualizado ${p.atualizado_em}</span>
        <select class="status-select" onchange="atualizarStatus('${p.id}',this.value)">${opts}</select>
      </div>
    </div>`;
}

async function atualizarStatus(id,status){
  try{
    const res=await fetch(`${API}/cozinha/pedidos/${id}`,{
      method:"PATCH",
      headers:userHeaders({"Content-Type":"application/json"}),
      body:JSON.stringify({status}),
    });
    const data=await res.json();
    res.ok?(toast(`Status → ${STATUS_LABELS[status]||status}`),carregarCozinha()):toast(data.detail,"err");
  }catch{toast("Erro ao atualizar","err");}
}

setInterval(()=>{
  if(!userId) return;
  const pag=document.querySelector(".page.active");
  if(!pag) return;
  if(pag.id==="page-pedidos") carregarMeusPedidos();
  if(pag.id==="page-cozinha") carregarCozinha();
},5000);

if(userId) iniciarApp();
