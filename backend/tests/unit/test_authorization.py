# Creado por Aldo Garcia.
"""Contexto de usuario firmado y motor de politicas."""

from __future__ import annotations

import dataclasses

import pytest

from app.authorization.categories import CategoryPolicy, CategoryRegistry, validate_category_name
from app.authorization.context import UserContext
from app.authorization.policy import Effect, PolicyEngine
from app.common.errors import ConfigurationError, ForbiddenError
from tests.conftest import make_context

pytestmark = pytest.mark.unit


def build_registry(**overrides: bool) -> CategoryRegistry:
    names = (
        "prestaciones",
        "nomina",
        "reclutamiento",
        "relaciones_laborales",
        "salud_ambiental",
        "investigaciones_internas",
    )
    policies = {
        name: CategoryPolicy(
            name=name,
            wildcard_eligible=overrides.get(name, name != "investigaciones_internas"),
        )
        for name in names
    }
    return CategoryRegistry(
        policies=policies, default_wildcard_eligible=True, default_sensitivity="internal"
    )


@pytest.fixture()
def engine() -> PolicyEngine:
    return PolicyEngine(registry=build_registry())


class TestFirmaDelContexto:
    def test_un_contexto_firmado_se_verifica(self, secret: str):
        ctx = make_context()
        assert ctx.verify(secret) is True

    def test_un_contexto_sin_firma_no_se_verifica(self, secret: str):
        ctx = dataclasses.replace(make_context(), signature="")
        assert ctx.verify(secret) is False
        with pytest.raises(ForbiddenError):
            ctx.require_valid(secret)

    def test_manipular_los_roles_invalida_la_firma(self, secret: str):
        ctx = make_context(roles=frozenset({"prestaciones_reader_test"}))
        forjado = dataclasses.replace(ctx, roles=frozenset({"matrix_admin_test"}))
        assert forjado.verify(secret) is False

    def test_manipular_las_categorias_invalida_la_firma(self, secret: str):
        ctx = make_context(categories=frozenset({"prestaciones"}), wildcard=False)
        forjado = dataclasses.replace(ctx, allowed_categories=frozenset({"prestaciones", "nomina"}))
        assert forjado.verify(secret) is False

    def test_una_clave_distinta_no_valida(self):
        assert make_context().verify("otra-clave-cualquiera") is False

    def test_el_contexto_es_inmutable(self):
        ctx = make_context()
        with pytest.raises(dataclasses.FrozenInstanceError):
            ctx.category_wildcard = False  # type: ignore[misc]

    def test_el_perfil_publico_no_expone_la_firma(self):
        profile = make_context().public_profile()
        assert "signature" not in profile
        assert "session_id" not in profile


class TestCategoriasEfectivas:
    def test_el_wildcard_enumera_categorias_conocidas(self, engine: PolicyEngine, admin_context):
        efectivas = engine.effective_categories(admin_context)
        assert "prestaciones" in efectivas
        assert "nomina" in efectivas
        assert len(efectivas) == 5

    def test_el_wildcard_no_alcanza_categorias_no_elegibles(self, engine: PolicyEngine, admin_context):
        assert "investigaciones_internas" not in engine.effective_categories(admin_context)

    def test_el_usuario_restringido_solo_ve_su_categoria(
        self, engine: PolicyEngine, restricted_context
    ):
        assert engine.effective_categories(restricted_context) == frozenset({"prestaciones"})

    def test_una_concesion_a_categoria_inexistente_no_abre_comodin(self, engine: PolicyEngine):
        ctx = make_context(categories=frozenset({"categoria_fantasma"}), wildcard=False)
        assert engine.effective_categories(ctx) == frozenset()


class TestMatrizDeAutorizacion:
    """Matriz de la seccion 6.1 evaluada en la capa de politicas."""

    @pytest.mark.parametrize(
        "category",
        ["prestaciones", "nomina", "reclutamiento", "relaciones_laborales", "salud_ambiental"],
    )
    def test_matrix_tiene_acceso_a_todas(self, engine: PolicyEngine, admin_context, category: str):
        assert engine.can_read_category(admin_context, category).effect is Effect.ALLOW

    def test_matrixr1_accede_a_prestaciones(self, engine: PolicyEngine, restricted_context):
        assert engine.can_read_category(restricted_context, "prestaciones").allowed is True

    @pytest.mark.parametrize(
        "category", ["nomina", "reclutamiento", "relaciones_laborales", "salud_ambiental"]
    )
    def test_matrixr1_es_denegado_en_el_resto(
        self, engine: PolicyEngine, restricted_context, category: str
    ):
        decision = engine.can_read_category(restricted_context, category)
        assert decision.effect is Effect.DENY
        assert decision.reason == "deny_by_default"

    def test_categoria_nueva_denegada_para_restringido(self, engine: PolicyEngine, restricted_context):
        assert engine.can_read_category(restricted_context, "categoria_nueva").allowed is False

    def test_administracion_denegada_para_restringido(self, engine: PolicyEngine, restricted_context):
        assert engine.can_administer_knowledge(restricted_context).allowed is False
        assert engine.can_read_diagnostics(restricted_context).allowed is False

    def test_administracion_permitida_para_matrix(self, engine: PolicyEngine, admin_context):
        assert engine.can_administer_knowledge(admin_context).allowed is True

    def test_fuentes_estructuradas_denegadas_por_defecto(
        self, engine: PolicyEngine, restricted_context
    ):
        assert engine.can_query_source(restricted_context, "rh_demo").allowed is False

    def test_fuente_concedida_a_matrix(self, engine: PolicyEngine, admin_context):
        assert engine.can_query_source(admin_context, "rh_demo").allowed is True

    def test_fuente_no_concedida_se_deniega_aunque_haya_permiso(
        self, engine: PolicyEngine, admin_context
    ):
        assert engine.can_query_source(admin_context, "sap_hcm").allowed is False


class TestOwnershipDeConversaciones:
    def test_el_dueno_accede(self, engine: PolicyEngine, admin_context):
        assert engine.can_access_conversation(admin_context, admin_context.user_id).allowed is True

    def test_ni_siquiera_el_administrador_lee_conversaciones_ajenas(
        self, engine: PolicyEngine, admin_context
    ):
        assert engine.can_access_conversation(admin_context, "otro-usuario").allowed is False


class TestNombresDeCategoria:
    @pytest.mark.parametrize("name", ["prestaciones", "salud_ambiental", "area-01"])
    def test_nombres_validos(self, name: str):
        assert validate_category_name(name) == name

    @pytest.mark.parametrize(
        "name", ["../etc", "C:\\windows", "nomina/../secreto", "Nomina Confidencial", "", "a" * 100]
    )
    def test_nombres_invalidos_se_rechazan(self, name: str):
        with pytest.raises(ConfigurationError):
            validate_category_name(name)

    def test_se_normaliza_a_minusculas(self):
        assert validate_category_name("  PRESTACIONES  ") == "prestaciones"


class TestHashDeRoles:
    def test_es_estable_e_independiente_del_orden(self):
        a = make_context(roles=frozenset({"rol_a", "rol_b"}))
        b = make_context(roles=frozenset({"rol_b", "rol_a"}))
        assert a.role_set_hash == b.role_set_hash

    def test_roles_distintos_producen_hash_distinto(self):
        a = make_context(roles=frozenset({"rol_a"}))
        b = make_context(roles=frozenset({"rol_b"}))
        assert a.role_set_hash != b.role_set_hash

    def test_no_revela_los_nombres_de_rol(self):
        ctx: UserContext = make_context(roles=frozenset({"matrix_admin_test"}))
        assert "matrix_admin_test" not in ctx.role_set_hash
