
document.addEventListener("DOMContentLoaded", function () {

    const botaoTema = document.getElementById("themeToggle");

    // Aplicar o tema escolhido
    function aplicarTema(tema) {
        document.documentElement.setAttribute("data-theme", tema);

        if (botaoTema) {
            botaoTema.setAttribute(
                "aria-label",
                tema === "dark" ? "Ativar tema claro" : "Ativar tema escuro"
            );

            botaoTema.setAttribute(
                "title",
                tema === "dark" ? "Ativar tema claro" : "Ativar tema escuro"
            );
        }
    }

    // Carregar o tema salvo
    let temaSalvo = localStorage.getItem("tema") || "light";

    aplicarTema(temaSalvo);

    // Alternar entre tema claro e escuro
    if (botaoTema) {
        botaoTema.addEventListener("click", function () {

            temaSalvo = temaSalvo === "light" ? "dark" : "light";

            localStorage.setItem("tema", temaSalvo);

            aplicarTema(temaSalvo);
        });
    }

    // Animação das mensagens
    document.querySelectorAll(".alert").forEach((alert) => {
        window.setTimeout(() => {
            alert.classList.add("fade");
        }, 4500);
    });

});
