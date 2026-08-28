"""La découverte, face à un projet qui ressemble à un vrai projet.

Un projet réel est un package : des modules qui s'importent entre eux avec
`from . import ...`. Ces tests-là existent parce que la découverte ne le
supportait pas, et que rien ne le disait avant l'exécution.
"""

import textwrap

import pytest

from gwenlake.training import discover


def _projet(racine, fichiers: dict):
    for chemin, source in fichiers.items():
        cible = racine / chemin
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_text(textwrap.dedent(source))
    return racine


@pytest.fixture
def package(tmp_path, monkeypatch):
    monkeypatch.setenv("GWENLAKE_RUN_DIR", str(tmp_path / "runs"))
    return _projet(tmp_path, {
        "src/monpkg/__init__.py": "",
        "src/monpkg/noyau.py": 'VALEUR = "voisin"\n',
        "src/monpkg/entree.py": """
            from gwenlake.training import train

            @train(steps=1, model="essai", tracking=False)
            def fit(run):
                from . import noyau
                return {"vu": noyau.VALEUR}
        """,
    })


def test_a_decorated_function_is_found_inside_a_package(package):
    assert list(discover(package)) == ["fit"]


def test_the_function_can_import_its_siblings(package):
    """Le cœur du sujet.

    Importer un fichier sous un nom inventé lui laisse `__package__` vide, et
    tout import relatif échoue alors — `attempted relative import with no
    known parent package`. La découverte trouvait quand même la fonction,
    puisque le décorateur est au niveau du module : l'échec n'arrivait qu'à
    l'appel, dans le pod, après le téléchargement des données.
    """
    fit = discover(package)["fit"]
    assert fit(None) == {"vu": "voisin"}


def test_the_module_keeps_its_real_name(package):
    """Le nom est ce qui rend l'import relatif résoluble ; le vérifier ici
    évite de dépendre du seul test ci-dessus pour le voir régresser."""
    assert discover(package)["fit"].__module__ == "monpkg.entree"


def test_a_loose_script_is_still_found(tmp_path, monkeypatch):
    """Un fichier hors package n'a pas d'import relatif à satisfaire, et son
    nom nu pourrait entrer en collision avec un module installé."""
    monkeypatch.setenv("GWENLAKE_RUN_DIR", str(tmp_path / "runs"))
    racine = _projet(tmp_path, {
        "src/script.py": """
            from gwenlake.training import train

            @train(steps=1, model="essai", tracking=False)
            def fit(run):
                return {"ok": True}
        """,
    })
    assert list(discover(racine)) == ["fit"]
