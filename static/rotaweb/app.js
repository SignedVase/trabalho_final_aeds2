"use strict";

const porId = (id) => document.getElementById(id);
const formulario = porId("consulta");
const catalogo = JSON.parse(porId("catalogo").textContent);
const limpar = (texto) => texto.normalize("NFD").replace(/\p{Diacritic}/gu, "")
  .toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
const indice = new Map();
function indexar({ endereco, busca = "", cep = "" }) {
  const nome = limpar(endereco.split(",")[0]);
  const texto = limpar([endereco, busca, cep, cep.replace("-", "")].join(" "));
  indice.set(limpar(endereco) + "|" + cep, { endereco, cep, nome, palavras: texto.split(" ") });
}
catalogo.forEach(indexar);

let cargaLogradouros;
function carregarLogradouros() {
  if (!cargaLogradouros) {
    cargaLogradouros = fetch(formulario.dataset.logradouros)
      .then((resposta) => resposta.ok ? resposta.json() : null)
      .then((catalogo) => {
        if (!catalogo) return false;
        catalogo.ruas.forEach(indexar);
        return true;
      })
      .catch(() => false);
  }
  return cargaLogradouros;
}

function instalarSugestoes(campo) {
  const lista = porId("lista-" + campo.id);
  let sugestoes = [];
  let ativo = -1;
  campo.setAttribute("role", "combobox");
  campo.setAttribute("aria-autocomplete", "list");
  campo.setAttribute("aria-controls", lista.id);
  campo.setAttribute("aria-expanded", "false");

  function fechar() {
    lista.hidden = true;
    ativo = -1;
    campo.setAttribute("aria-expanded", "false");
    campo.removeAttribute("aria-activedescendant");
  }

  function escolher(posicao) {
    campo.value = sugestoes[posicao].endereco;
    fechar();
  }

  function sugerir() {
    fechar();
    const pesquisa = limpar(campo.value);
    if (pesquisa.length < 2) return;
    const termos = pesquisa.split(" ");
    const prioridade = (nome) => nome === pesquisa ? 0 : nome.startsWith(pesquisa) ? 1 : 2;
    sugestoes = Array.from(indice.values())
      .filter(({ palavras }) => termos.every((termo) => palavras.some((palavra) => palavra.startsWith(termo))))
      .sort((a, b) => prioridade(a.nome) - prioridade(b.nome))
      .slice(0, 8);
    if (!sugestoes.length) return;
    lista.replaceChildren(...sugestoes.map(({ endereco, cep }, posicao) => {
      const item = document.createElement("li");
      item.id = lista.id + "-" + posicao;
      item.setAttribute("role", "option");
      item.setAttribute("aria-selected", "false");
      const [rua, ...local] = endereco.split(", ");
      const titulo = document.createElement("strong");
      titulo.textContent = rua;
      const complemento = document.createElement("small");
      complemento.textContent = [local.join(", "), cep && "CEP " + cep].filter(Boolean).join(" · ");
      item.append(titulo, complemento);
      item.addEventListener("pointerdown", (evento) => evento.preventDefault());
      item.addEventListener("click", () => escolher(posicao));
      return item;
    }));
    lista.hidden = false;
    campo.setAttribute("aria-expanded", "true");
  }

  campo.addEventListener("input", sugerir);
  campo.addEventListener("focus", () => {
    sugerir();
    carregarLogradouros().then((atualizado) => {
      if (atualizado && document.activeElement === campo && ativo < 0) sugerir();
    });
  });
  campo.addEventListener("blur", fechar);
  campo.addEventListener("keydown", (evento) => {
    if (evento.key === "Escape") {
      fechar();
      return;
    }
    if (lista.hidden && evento.key === "ArrowDown") sugerir();
    if (lista.hidden) return;
    if (evento.key === "Enter" && ativo >= 0) {
      evento.preventDefault();
      escolher(ativo);
    }
    if (evento.key === "ArrowDown" || evento.key === "ArrowUp") {
      evento.preventDefault();
      const direcao = evento.key === "ArrowDown" ? 1 : -1;
      ativo = ativo < 0 && direcao === -1
        ? sugestoes.length - 1 : (ativo + direcao + sugestoes.length) % sugestoes.length;
      Array.from(lista.children).forEach((item, i) => item.setAttribute("aria-selected", String(i === ativo)));
      campo.setAttribute("aria-activedescendant", lista.children[ativo].id);
    }
  });
}

instalarSugestoes(porId("origem"));
instalarSugestoes(porId("destino"));

const leaflet = window.L;
const mapa = leaflet?.map("mapa").setView([-19.875833, -44.983889], 14);
const camadas = mapa && leaflet.featureGroup().addTo(mapa);
const aviso = porId("mapa-aviso");
if (mapa) {
  const blocos = leaflet.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> · <a href="https://www.openstreetmap.org/fixthemap">Corrigir mapa</a>',
    maxZoom: 19,
    referrerPolicy: "strict-origin-when-cross-origin",
  }).addTo(mapa);
  blocos.on("tileerror", () => {
    aviso.textContent = "O mapa de fundo não carregou. Os trajetos continuam disponíveis.";
    aviso.hidden = false;
  });
} else {
  aviso.textContent = "Mapa interativo indisponível. As rotas serão exibidas como um traçado esquemático.";
  aviso.hidden = false;
}

const DISTANCIA = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 });
const distancia = (rota) => DISTANCIA.format(rota.metros / 1000) + " km";
function duracao(rota) {
  const minutos = Math.round(rota.segundos / 60);
  if (!minutos) return "< 1 min";
  if (minutos < 60) return minutos + " min";
  return Math.floor(minutos / 60) + " h " + (minutos % 60) + " min";
}

function estilo(ativo) {
  return { color: ativo ? "#08735b" : "#687e97", weight: ativo ? 7 : 5, opacity: ativo ? 1 : .72 };
}

function esquema(resultado, selecionada) {
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.classList.add("esquema");
  svg.setAttribute("viewBox", "0 0 640 420");
  const pontos = resultado.rotas.flatMap((rota) => rota.geometria.coordinates);
  let [minX, minY] = pontos[0];
  let [maxX, maxY] = pontos[0];
  for (const [x, y] of pontos) {
    minX = Math.min(minX, x);
    maxX = Math.max(maxX, x);
    minY = Math.min(minY, y);
    maxY = Math.max(maxY, y);
  }
  const escala = Math.min(560 / Math.max(maxX - minX, 1e-8), 340 / Math.max(maxY - minY, 1e-8));
  const projetar = ([x, y]) => [320 + (x - (maxX + minX) / 2) * escala, 210 - (y - (maxY + minY) / 2) * escala];
  const ordem = resultado.rotas.map((_, i) => i).filter((i) => i !== selecionada).concat(selecionada);
  for (const i of ordem) {
    const linha = document.createElementNS(NS, "polyline");
    linha.setAttribute("points", resultado.rotas[i].geometria.coordinates.map(projetar).join(" "));
    linha.setAttribute("fill", "none");
    linha.setAttribute("stroke", estilo(i === selecionada).color);
    linha.setAttribute("stroke-width", estilo(i === selecionada).weight);
    linha.setAttribute("stroke-linejoin", "round");
    svg.append(linha);
  }
  const selecionadaPontos = resultado.rotas[selecionada].geometria.coordinates;
  for (const [letra, ponto] of [["A", selecionadaPontos[0]], ["B", selecionadaPontos.at(-1)]]) {
    const [x, y] = projetar(ponto);
    const rotulo = document.createElementNS(NS, "text");
    rotulo.setAttribute("x", x);
    rotulo.setAttribute("y", y - 10);
    rotulo.setAttribute("text-anchor", "middle");
    rotulo.textContent = letra;
    svg.append(rotulo);
  }
  porId("mapa").replaceChildren(svg);
}

function exibir(resultado, demo) {
  const { rotas, partida, chegada } = resultado;
  const linhas = camadas ? rotas.map((rota) => leaflet.geoJSON(rota.geometria, {
    style: { smoothFactor: 0 },
  }).addTo(camadas)) : [];
  const marcadores = [];
  if (camadas) {
    for (const letra of ["A", "B"]) {
      marcadores.push(leaflet.circleMarker([0, 0], {
        radius: 7, color: "#fff", fillColor: "#15382f", fillOpacity: 1, weight: 2,
      }).bindTooltip(letra, { permanent: true, direction: "top" }));
    }
    mapa.fitBounds(camadas.getBounds(), { padding: [35, 35], maxZoom: 17 });
  }

  function selecionar(i) {
    porId("resumo").textContent = [demo ? "Demonstração" : "", distancia(rotas[i]), duracao(rotas[i])]
      .filter(Boolean).join(" · ");
    if (camadas) {
      linhas.forEach((linha, posicao) => linha.setStyle(estilo(posicao === i)));
      linhas[i].bringToFront();
      const pontos = rotas[i].geometria.coordinates;
      [pontos[0], pontos.at(-1)].forEach(([lon, lat], indice) => {
        marcadores[indice].setLatLng([lat, lon]).addTo(camadas).bringToFront();
      });
    } else {
      esquema(resultado, i);
    }
  }

  porId("alternativas").replaceChildren(...rotas.map((rota, i) => {
    const cartao = document.createElement("label");
    cartao.className = "rota";
    const radio = document.createElement("input");
    radio.type = "radio";
    radio.name = "rota";
    radio.checked = i === 0;
    radio.addEventListener("change", () => selecionar(i));
    const titulo = document.createElement("span");
    titulo.textContent = i === 0 ? "Menor distância" : "Alternativa " + i;
    const valores = document.createElement("small");
    valores.textContent = distancia(rota) + " · " + duracao(rota);
    cartao.append(radio, titulo, valores);
    return cartao;
  }));

  porId("opcoes").hidden = false;
  porId("locais").textContent = "A · " + partida.endereco + "  |  B · " + chegada.endereco;
  porId("locais").hidden = false;
  selecionar(0);
}

async function consultar(demo) {
  const botoes = Array.from(formulario.querySelectorAll("button"));
  if (botoes.some((botao) => botao.disabled)) return;
  botoes.forEach((botao) => { botao.disabled = true; });
  const status = porId("status");
  status.classList.remove("erro");
  status.textContent = "Calculando rotas…";
  porId("opcoes").hidden = true;
  porId("locais").hidden = true;
  porId("resumo").textContent = "Nova Serrana, MG";
  if (camadas) camadas.clearLayers();
  else porId("mapa").replaceChildren();

  try {
    const dados = Object.fromEntries(new FormData(formulario));
    const resposta = demo ? await fetch(porId("demo").dataset.url) : await fetch(formulario.action, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": dados.csrfmiddlewaretoken },
      body: JSON.stringify({ nome: dados.nome, origem: dados.origem, destino: dados.destino }),
    });
    const resultado = await resposta.json();
    if (!resposta.ok) throw new Error(resultado.erro);
    if (!demo) {
      for (const endereco of [dados.origem.trim(), dados.destino.trim()]) {
        if (!Array.from(indice.values()).some((item) => limpar(item.endereco) === limpar(endereco))) {
          indexar({ endereco });
        }
      }
    }
    exibir(resultado, demo);
    status.textContent = demo ? "Demonstração com trajetos calculados pelo OSRM."
      : resultado.rotas.length === 1 ? "Uma rota disponível para este trajeto."
      : resultado.rotas.length + " rotas disponíveis. Selecione uma para comparar.";
  } catch (erro) {
    status.classList.add("erro");
    status.textContent = erro instanceof SyntaxError || erro instanceof TypeError
      ? "Não foi possível completar a consulta. Tente novamente." : erro.message;
  } finally {
    botoes.forEach((botao) => { botao.disabled = false; });
  }
}

formulario.addEventListener("submit", (evento) => {
  evento.preventDefault();
  consultar(false);
});
porId("demo").addEventListener("click", () => consultar(true));
