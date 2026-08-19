# Creado por Aldo Garcia.
"""``QueryPolicyValidator``: valida un plan contra permisos y esquema.

Se ejecuta **antes** de compilar SQL. Comprueba, en este orden:

1. que la fuente exista, este habilitada y el rol la tenga concedida;
2. que la entidad este declarada en la configuracion;
3. que **cada** columna referenciada (proyeccion, filtro, agrupacion, orden,
   agregacion) este en la allowlist de la entidad;
4. que el limite no exceda el maximo de la entidad/fuente;
5. que los filtros organizacionales obligatorios se apliquen.

Deny-by-default: cualquier duda termina en rechazo.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.authorization.context import UserContext
from app.authorization.policy import PolicyEngine
from app.common.errors import ForbiddenError, StructuredQueryRejectedError
from app.common.logging import get_logger
from app.structured_data.schemas import QueryFilter, StructuredQueryPlan
from app.structured_data.sources import EntityConfig, SourceCatalog, SourceConfig, get_source_catalog

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ValidatedPlan:
    """Plan aprobado, con la configuracion resuelta y los filtros obligatorios."""

    plan: StructuredQueryPlan
    source: SourceConfig
    entity: EntityConfig
    effective_limit: int
    injected_filters: tuple[QueryFilter, ...] = field(default_factory=tuple)

    def all_filters(self) -> tuple[QueryFilter, ...]:
        return tuple(self.plan.filters) + self.injected_filters


class QueryPolicyValidator:
    """Valida planes de consulta contra politicas y esquema declarado."""

    def __init__(
        self,
        *,
        catalog: SourceCatalog | None = None,
        policy_engine: PolicyEngine | None = None,
    ) -> None:
        self._catalog = catalog or get_source_catalog()
        self._policies = policy_engine

    def validate(self, plan: StructuredQueryPlan, *, ctx: UserContext) -> ValidatedPlan:
        source = self._catalog.get(plan.source)
        if source is None:
            logger.warning("structured.unknown_source", extra={"source_name": plan.source})
            raise StructuredQueryRejectedError("La fuente solicitada no esta disponible.")
        if not source.enabled:
            raise StructuredQueryRejectedError("La fuente solicitada no esta habilitada.")

        # --- autorizacion de la fuente ------------------------------------
        if self._policies is not None:
            decision = self._policies.can_query_source(ctx, source.name)
            if not decision.allowed:
                logger.warning(
                    "structured.source_denied",
                    extra={
                        "source_name": source.name,
                        "authorization_decision": "DENY",
                        "deny_reason": decision.reason,
                    },
                )
                raise ForbiddenError()
        elif source.allowed_roles and not (set(source.allowed_roles) & set(ctx.roles)):
            raise ForbiddenError()

        # --- entidad -------------------------------------------------------
        entity = source.entity(plan.entity)
        if entity is None:
            logger.warning(
                "structured.unknown_entity",
                extra={"source_name": source.name, "entity_name": plan.entity},
            )
            raise StructuredQueryRejectedError("La entidad solicitada no esta disponible.")

        allowed_columns = set(entity.allowed_columns)
        if not allowed_columns:
            raise StructuredQueryRejectedError("La entidad no tiene columnas habilitadas.")

        # --- columnas ------------------------------------------------------
        referenced = plan.referenced_columns()
        forbidden = sorted(referenced - allowed_columns)
        if forbidden:
            logger.warning(
                "structured.column_denied",
                extra={"source_name": source.name, "entity_name": entity.name, "denied_count": len(forbidden)},
            )
            raise StructuredQueryRejectedError("La consulta referencia campos no autorizados.")

        if not plan.fields and not plan.aggregations:
            raise StructuredQueryRejectedError("El plan debe proyectar campos o agregaciones.")

        # Una agregacion sin group_by no puede mezclarse con campos sueltos: el
        # resultado seria ambiguo y depende del motor.
        if plan.aggregations and plan.fields and not plan.group_by:
            raise StructuredQueryRejectedError(
                "Una consulta con agregaciones requiere group_by para los campos proyectados."
            )
        if plan.group_by and not set(plan.group_by).issubset(set(plan.fields)):
            raise StructuredQueryRejectedError("group_by debe estar contenido en los campos proyectados.")

        # --- limites -------------------------------------------------------
        effective_limit = min(plan.limit, entity.max_rows, source.max_rows)

        # --- filtros organizacionales obligatorios --------------------------
        injected: list[QueryFilter] = []
        declared_fields = {f.field for f in plan.filters}
        for column, value in entity.required_filters.items():
            if column not in allowed_columns:
                raise StructuredQueryRejectedError(
                    "La configuracion de la entidad exige un filtro sobre una columna no permitida."
                )
            if column in declared_fields:
                # El plan ya filtra por esa columna: se conserva el filtro
                # obligatorio ademas del suyo, nunca en su lugar.
                pass
            injected.append(
                QueryFilter.model_validate({"field": column, "operator": "eq", "value": value})
            )

        return ValidatedPlan(
            plan=plan,
            source=source,
            entity=entity,
            effective_limit=effective_limit,
            injected_filters=tuple(injected),
        )
