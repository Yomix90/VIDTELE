"""Rendu du tableau de bord d'administration (données réelles, plus de valeurs inventées)."""


async def test_tableau_de_bord_affiche_les_donnees_reelles(client, admin_token):
    client.cookies.set("admin_token", admin_token)
    try:
        res = await client.get("/admin")
    finally:
        client.cookies.clear()
    assert res.status_code == 200
    page = res.text
    for bloc in ("Lectures par jour", "Qualité de lecture", "Spectateurs", "Vidéos à classer", "Nouveaux comptes"):
        assert bloc in page, bloc
    # Ancien graphique : valeurs écrites en dur dans le modèle
    assert "12, 19, 15, 25, 22, 30" not in page
    # Classe Bootstrap inexistante qui rendait l'icône Telegram invisible
    assert "bg-opacity-20" not in page


async def test_tableau_de_bord_reserve_aux_admins(client):
    res = await client.get("/admin", follow_redirects=False)
    assert res.status_code in (302, 303, 307)
