// Liste de blocs réordonnable par glisser-déposer (poignée ≡) avec suppression.
// `Sortable` est défini devant ce fichier par __init__.py (SortableJS enveloppé, sans variable globale).
//
// data : { items: [{ id, titre, apercu }] }
// Événements envoyés à Python :
//   reorder -> la liste des id dans le nouvel ordre
//   delete  -> l'id du bloc à supprimer
// Tout texte venant des données passe par textContent : jamais d'innerHTML.

const SVG_NS = "http://www.w3.org/2000/svg";

function creerPoignee() {
  const poignee = document.createElement("span");
  poignee.className = "sb-poignee";
  poignee.setAttribute("role", "button");
  poignee.setAttribute("aria-label", "Déplacer le bloc : maintenir et glisser");
  poignee.title = "Maintenir et glisser pour déplacer";

  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 0 20 20");
  svg.setAttribute("width", "20");
  svg.setAttribute("height", "20");
  svg.setAttribute("aria-hidden", "true");
  for (const y of [5, 10, 15]) {
    const trait = document.createElementNS(SVG_NS, "line");
    trait.setAttribute("x1", "3");
    trait.setAttribute("x2", "17");
    trait.setAttribute("y1", String(y));
    trait.setAttribute("y2", String(y));
    trait.setAttribute("stroke", "currentColor");
    trait.setAttribute("stroke-width", "2");
    trait.setAttribute("stroke-linecap", "round");
    svg.appendChild(trait);
  }
  poignee.appendChild(svg);
  return poignee;
}

function creerLigne(item, setTriggerValue) {
  const ligne = document.createElement("div");
  ligne.className = "sb-ligne";
  ligne.dataset.id = item.id;

  const numero = document.createElement("span");
  numero.className = "sb-numero";

  const texte = document.createElement("div");
  texte.className = "sb-texte";
  const titre = document.createElement("div");
  titre.className = "sb-titre";
  titre.textContent = item.titre || "Bloc";
  texte.appendChild(titre);
  if (item.apercu) {
    const apercu = document.createElement("div");
    apercu.className = "sb-apercu";
    apercu.textContent = item.apercu;
    texte.appendChild(apercu);
  }

  const supprimer = document.createElement("button");
  supprimer.type = "button";
  supprimer.className = "sb-supprimer";
  supprimer.setAttribute("aria-label", "Supprimer ce bloc");
  supprimer.title = "Supprimer ce bloc";
  supprimer.textContent = "🗑️";
  supprimer.addEventListener("click", () => setTriggerValue("delete", item.id));

  ligne.append(creerPoignee(), numero, texte, supprimer);
  return ligne;
}

function numeroter(racine) {
  [...racine.children].forEach((ligne, i) => {
    ligne.querySelector(".sb-numero").textContent = `${i + 1}.`;
  });
}

// Streamlit rappelle cette fonction à chaque changement de données SANS appeler d'abord le
// nettoyage de l'appel précédent : sans mémoire, chaque rafraîchissement ajouterait une liste.
// On retient donc, par conteneur, la liste déjà montée pour la remplacer.
const MONTEES = new WeakMap();

function demonter(parentElement) {
  const precedente = MONTEES.get(parentElement);
  if (!precedente) return;
  precedente.sortable.destroy();
  precedente.racine.remove();
  MONTEES.delete(parentElement);
}

export default function (component) {
  const { data, parentElement, setTriggerValue } = component;
  const items = (data && data.items) || [];

  demonter(parentElement);

  const racine = document.createElement("div");
  racine.className = "sb-liste";
  for (const item of items) racine.appendChild(creerLigne(item, setTriggerValue));
  numeroter(racine);
  parentElement.appendChild(racine);

  // Le clone qui suit la souris pendant le glissement est rangé dans la liste : on l'ignore.
  const ordre = () =>
    [...racine.children]
      .filter((ligne) => !ligne.classList.contains("sb-glisse"))
      .map((ligne) => ligne.dataset.id);
  let ordreInitial = ordre();

  const sortable = Sortable.create(racine, {
    handle: ".sb-poignee",
    animation: 150,
    // Mode « fallback » : mêmes événements souris et tactiles partout (le glisser-déposer
    // HTML5 natif n'existe pas sur écran tactile) ; pas de décalage avant de saisir la poignée.
    forceFallback: true,
    fallbackTolerance: 3,
    ghostClass: "sb-fantome",
    chosenClass: "sb-choisi",
    fallbackClass: "sb-glisse",
    onSort: () => numeroter(racine),
    onEnd: () => {
      const nouvelOrdre = ordre();
      if (nouvelOrdre.join("\n") !== ordreInitial.join("\n")) {
        ordreInitial = nouvelOrdre;
        setTriggerValue("reorder", nouvelOrdre);
      }
    },
  });

  MONTEES.set(parentElement, { racine, sortable });

  return () => {
    // Ne démonter que notre propre montage : un appel plus récent a pu en créer un autre.
    const courante = MONTEES.get(parentElement);
    if (courante && courante.racine === racine) demonter(parentElement);
  };
}
