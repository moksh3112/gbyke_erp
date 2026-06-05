from sqlalchemy import (
    Column, String, Integer, Float, Boolean,
    DateTime, ForeignKey, Text, Enum, Date
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


# ── ENUMS ─────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    superadmin = "superadmin"
    manager = "manager"
    staff = "staff"

class VehicleStatus(str, enum.Enum):
    manufacturing_pending = "manufacturing_pending"
    manufacturing_done    = "manufacturing_done"
    pdi_pending           = "pdi_pending"
    pdi_in_progress       = "pdi_in_progress"
    pdi_done              = "pdi_done"
    delivered             = "delivered"

class PDIResult(str, enum.Enum):
    passed  = "pass"
    failed  = "fail"
    rework  = "rework"

class StockMovementType(str, enum.Enum):
    received            = "received"
    consumed            = "consumed"
    defective           = "defective"
    damaged             = "damaged"
    scrapped            = "scrapped"
    transferred         = "transferred"
    adjusted            = "adjusted"
    returned            = "returned"
    correction_remove   = "correction_remove"

class ShipmentStatus(str, enum.Enum):
    pending  = "pending"
    received = "received"
    partial  = "partial"
    closed   = "closed"

class TransferStatus(str, enum.Enum):
    pending    = "pending"
    in_transit = "in_transit"
    completed  = "completed"
    cancelled  = "cancelled"


class DamageStage(str, enum.Enum):
    import_receiving = "import_receiving"
    warehouse        = "warehouse"
    manufacturing    = "manufacturing"
    pdi              = "pdi"
    transit          = "transit"
    dealer           = "dealer"

class AssemblyStatus(str, enum.Enum):
    pending     = "pending"
    in_progress = "in_progress"
    completed   = "completed"
    cancelled   = "cancelled"


# ── USERS ─────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id              = Column(String, primary_key=True, default=gen_uuid)
    full_name       = Column(String(100), nullable=False)
    username        = Column(String(50), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role            = Column(Enum(UserRole), nullable=False, default=UserRole.staff)
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), onupdate=func.now())


# ── MASTER DATA (MODELS, COLORS, BATTERIES) ───────────────────

class ScooterModel(Base):
    __tablename__ = "scooter_models"

    id          = Column(String, primary_key=True, default=gen_uuid)
    model_name  = Column(String(100), nullable=False, unique=True)
    model_code  = Column(String(30),  unique=True, nullable=False)
    description = Column(Text)
    is_active   = Column(Boolean, default=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    bom_items = relationship(
        "BOMItem", back_populates="model",
        cascade="all, delete-orphan"
    )


class MasterColor(Base):
    __tablename__ = "master_colors"

    id   = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, unique=True, nullable=False)


class MasterBattery(Base):
    __tablename__ = "master_batteries"

    id           = Column(String, primary_key=True, default=gen_uuid)
    battery_type = Column(String, nullable=False) # e.g., "Lithium Ion" or "Lead Acid"
    power_spec   = Column(String, nullable=False) # e.g., "72V 30Ah"


# ── LOCATIONS ─────────────────────────────────────────────────

class Location(Base):
    __tablename__ = "locations"

    id            = Column(String, primary_key=True, default=gen_uuid)
    name          = Column(String(100), nullable=False, unique=True)
    location_type = Column(String(30), nullable=False)  # factory / warehouse / godown
    address       = Column(Text)
    city          = Column(String(50))
    state         = Column(String(50))
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())


# ── INVENTORY ─────────────────────────────────────────────────

class InventoryCategory(Base):
    __tablename__ = "inventory_categories"

    id          = Column(String, primary_key=True, default=gen_uuid)
    name        = Column(String(100), nullable=False, unique=True)
    description = Column(Text)

    items = relationship("InventoryItem", back_populates="category")


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id                  = Column(String, primary_key=True, default=gen_uuid)
    item_name           = Column(String(150), nullable=False)
    sku                 = Column(String(80), unique=True, nullable=False, index=True)
    category_id         = Column(String, ForeignKey("inventory_categories.id"))
    unit                = Column(String(20), default="pcs")
    total_quantity      = Column(Integer, default=0)
    remaining_quantity  = Column(Integer, default=0)
    consumed_quantity   = Column(Integer, default=0)
    defective_quantity  = Column(Integer, default=0)
    damaged_quantity    = Column(Integer, default=0)
    low_stock_threshold = Column(Integer, default=10)
    unit_cost           = Column(Float, default=0.0)
    is_spare_part       = Column(Boolean, default=False)
    model_name          = Column(String(100), nullable=True)
    colour              = Column(String(50),  nullable=True)
    import_date         = Column(Date, nullable=True)
    location_id         = Column(String, ForeignKey("locations.id"), nullable=True)
    is_active           = Column(Boolean, default=True)
    created_at          = Column(DateTime(timezone=True), server_default=func.now())
    updated_at          = Column(DateTime(timezone=True), onupdate=func.now())

    category        = relationship("InventoryCategory", back_populates="items")
    stock_movements = relationship("StockMovement", back_populates="item")
    bom_items       = relationship("BOMItem", back_populates="inventory_item")
    location        = relationship("Location", foreign_keys=[location_id])


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id             = Column(String, primary_key=True, default=gen_uuid)
    item_id        = Column(String, ForeignKey("inventory_items.id"), nullable=False)
    movement_type  = Column(Enum(StockMovementType), nullable=False)
    quantity       = Column(Integer, nullable=False)
    location_id    = Column(String, ForeignKey("locations.id"))
    reference_id   = Column(String)
    reference_type = Column(String(50))
    notes          = Column(Text)
    performed_by   = Column(String, ForeignKey("users.id"))
    created_at     = Column(DateTime(timezone=True), server_default=func.now())

    item = relationship("InventoryItem", back_populates="stock_movements")


# ── BILL OF MATERIALS ─────────────────────────────────────────
class BOMItem(Base):
    __tablename__ = "bom_items"

    id                  = Column(String, primary_key=True, default=gen_uuid)
    model_id            = Column(String, ForeignKey("scooter_models.id"), nullable=False)
    part_name           = Column(String(150), nullable=True)
    sku                 = Column(String(80), nullable=True)
    inventory_item_id   = Column(String, ForeignKey("inventory_items.id"), nullable=True)
    quantity_required   = Column(Integer, nullable=False)
    colour              = Column(String(50), nullable=True)
    battery_type        = Column(String(50), nullable=True)
    power_spec          = Column(String(50), nullable=True)
    notes               = Column(Text)

    model          = relationship("ScooterModel", back_populates="bom_items")
    inventory_item = relationship("InventoryItem", back_populates="bom_items")

# ── ASSEMBLY JOBS ─────────────────────────────────────────────

class AssemblyJob(Base):
    __tablename__ = "assembly_jobs"

    id           = Column(String, primary_key=True, default=gen_uuid)
    model_id     = Column(String, ForeignKey("scooter_models.id"), nullable=False)
    color        = Column(String(50), nullable=True)
    battery_type = Column(String(50), nullable=True)
    power_spec   = Column(String(50), nullable=True)
    
    quantity     = Column(Integer, nullable=False)
    location_id  = Column(String, ForeignKey("locations.id"))
    status       = Column(Enum(AssemblyStatus), default=AssemblyStatus.pending)
    started_at   = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    performed_by = Column(String, ForeignKey("users.id"))
    notes        = Column(Text)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

    model         = relationship("ScooterModel")
    scooter_units = relationship("ScooterUnit", back_populates="assembly_job")


# ── SCOOTER UNITS (finished vehicles) ────────────────────────

class ScooterUnit(Base):
    __tablename__ = "scooter_units"

    id                    = Column(String, primary_key=True, default=gen_uuid)
    serial_number         = Column(String(100), unique=True, nullable=False, index=True)
    chassis_number        = Column(String(100), unique=True, nullable=True)
    pdi_number            = Column(String(50), nullable=True) # Added field
    motor_number          = Column(String(100), nullable=True)  # dedicated motor/serial field
    pdi_remarks           = Column(Text,        nullable=True)  # inspector notes
    model_id              = Column(String, ForeignKey("scooter_models.id"), nullable=False)
    color                 = Column(String(50), nullable=True)
    battery_type          = Column(String(50), nullable=True)
    power_spec            = Column(String(50), nullable=True)

    assembly_job_id       = Column(String, ForeignKey("assembly_jobs.id"))
    current_location_id   = Column(String, ForeignKey("locations.id"))
    current_dealer_id     = Column(String, ForeignKey("dealers.id"), nullable=True)
    status                = Column(Enum(VehicleStatus), default=VehicleStatus.manufacturing_pending)
    manufactured_date     = Column(Date)
    delivered_date        = Column(Date)
    created_at            = Column(DateTime(timezone=True), server_default=func.now())
    updated_at            = Column(DateTime(timezone=True), onupdate=func.now())

    model        = relationship("ScooterModel")
    assembly_job = relationship("AssemblyJob", back_populates="scooter_units")
    pdi_records  = relationship("PDIRecord", back_populates="scooter_unit")


# ── PDI RECORDS ───────────────────────────────────────────────

class PDIRecord(Base):
    __tablename__ = "pdi_records"

    id                = Column(String, primary_key=True, default=gen_uuid)
    scooter_unit_id   = Column(String, ForeignKey("scooter_units.id"), nullable=False)
    inspector_id      = Column(String, ForeignKey("users.id"))
    result            = Column(Enum(PDIResult), nullable=True)
    remarks           = Column(Text)
    failure_reason    = Column(Text)
    rework_notes      = Column(Text)
    started_at        = Column(DateTime(timezone=True))
    completed_at      = Column(DateTime(timezone=True))
    created_at        = Column(DateTime(timezone=True), server_default=func.now())

    scooter_unit = relationship("ScooterUnit", back_populates="pdi_records")


# ── SUPPLIERS & SHIPMENTS ─────────────────────────────────────

class Supplier(Base):
    __tablename__ = "suppliers"

    id              = Column(String, primary_key=True, default=gen_uuid)
    name            = Column(String(150), nullable=False)
    country         = Column(String(50), default="China")
    contact_name    = Column(String(100))
    contact_email   = Column(String(100))
    contact_phone   = Column(String(30))
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    shipments = relationship("Shipment", back_populates="supplier")


class Shipment(Base):
    __tablename__ = "shipments"

    id                 = Column(String, primary_key=True, default=gen_uuid)
    shipment_code      = Column(String(50), unique=True, nullable=False)
    supplier_id        = Column(String, ForeignKey("suppliers.id"))
    container_number   = Column(String(50))
    expected_arrival   = Column(Date)
    actual_arrival     = Column(Date)
    status             = Column(Enum(ShipmentStatus), default=ShipmentStatus.pending)
    notes              = Column(Text)
    received_by        = Column(String, ForeignKey("users.id"))
    created_at         = Column(DateTime(timezone=True), server_default=func.now())

    supplier = relationship("Supplier", back_populates="shipments")
    items    = relationship("ShipmentItem", back_populates="shipment")


class ShipmentItem(Base):
    __tablename__ = "shipment_items"

    id                  = Column(String, primary_key=True, default=gen_uuid)
    shipment_id         = Column(String, ForeignKey("shipments.id"), nullable=False)
    inventory_item_id   = Column(String, ForeignKey("inventory_items.id"), nullable=False)
    expected_quantity   = Column(Integer, nullable=False)
    received_quantity   = Column(Integer, default=0)
    damaged_quantity    = Column(Integer, default=0)
    shortage_quantity   = Column(Integer, default=0)
    notes               = Column(Text)

    shipment = relationship("Shipment", back_populates="items")


# ── DEALERS ───────────────────────────────────────────────────

class Dealer(Base):
    __tablename__ = "dealers"

    id            = Column(String, primary_key=True, default=gen_uuid)
    dealer_name   = Column(String(150), nullable=False)
    dealer_code   = Column(String(30), unique=True, nullable=False)
    contact_name  = Column(String(100))
    contact_phone = Column(String(30))
    contact_email = Column(String(100))
    address       = Column(Text)
    city          = Column(String(50))
    state         = Column(String(50))
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())


# ── DISPATCH NOTES ────────────────────────────────────────────

class DispatchNote(Base):
    __tablename__ = "dispatch_notes"

    id            = Column(String, primary_key=True, default=gen_uuid)
    dealer_id     = Column(String, ForeignKey("dealers.id"), nullable=False)
    dispatch_date = Column(Date, nullable=False)
    notes         = Column(Text)
    dispatched_by = Column(String, ForeignKey("users.id"))
    created_at    = Column(DateTime(timezone=True), server_default=func.now())

    dealer   = relationship("Dealer")
    scooters = relationship("DispatchNoteScooter", back_populates="dispatch_note", cascade="all, delete-orphan")
    parts    = relationship("DispatchNotePart",    back_populates="dispatch_note", cascade="all, delete-orphan")


class DispatchNoteScooter(Base):
    __tablename__ = "dispatch_note_scooters"

    id               = Column(String, primary_key=True, default=gen_uuid)
    dispatch_note_id = Column(String, ForeignKey("dispatch_notes.id"), nullable=False)
    scooter_unit_id  = Column(String, ForeignKey("scooter_units.id"), nullable=False)

    dispatch_note = relationship("DispatchNote", back_populates="scooters")
    scooter_unit  = relationship("ScooterUnit")


class DispatchNotePart(Base):
    __tablename__ = "dispatch_note_parts"

    id                = Column(String, primary_key=True, default=gen_uuid)
    dispatch_note_id  = Column(String, ForeignKey("dispatch_notes.id"), nullable=False)
    inventory_item_id = Column(String, ForeignKey("inventory_items.id"), nullable=True)
    location_id       = Column(String, ForeignKey("locations.id"), nullable=True)
    part_name         = Column(String(200), nullable=False)
    quantity          = Column(Integer, nullable=False)
    notes             = Column(Text)

    dispatch_note  = relationship("DispatchNote", back_populates="parts")
    inventory_item = relationship("InventoryItem")
    location       = relationship("Location")


# ── STOCK TRANSFERS ───────────────────────────────────────────

class StockTransfer(Base):
    __tablename__ = "stock_transfers"

    id                 = Column(String, primary_key=True, default=gen_uuid)
    from_location_id   = Column(String, ForeignKey("locations.id"), nullable=False)
    to_location_id     = Column(String, ForeignKey("locations.id"), nullable=False)
    transfer_type      = Column(String(30))
    status             = Column(Enum(TransferStatus), default=TransferStatus.pending)
    notes              = Column(Text)
    initiated_by       = Column(String, ForeignKey("users.id"))
    completed_at       = Column(DateTime(timezone=True))
    created_at         = Column(DateTime(timezone=True), server_default=func.now())

    items = relationship("StockTransferItem", back_populates="transfer")


class StockTransferItem(Base):
    __tablename__ = "stock_transfer_items"

    id                  = Column(String, primary_key=True, default=gen_uuid)
    transfer_id         = Column(String, ForeignKey("stock_transfers.id"), nullable=False)
    inventory_item_id   = Column(String, ForeignKey("inventory_items.id"), nullable=True)
    scooter_unit_id     = Column(String, ForeignKey("scooter_units.id"), nullable=True)
    quantity            = Column(Integer, default=1)

    transfer = relationship("StockTransfer", back_populates="items")


# ── DAMAGE RECORDS ────────────────────────────────────────────

class DamageRecord(Base):
    __tablename__ = "damage_records"

    id                  = Column(String, primary_key=True, default=gen_uuid)
    stage               = Column(Enum(DamageStage), nullable=False)
    inventory_item_id   = Column(String, ForeignKey("inventory_items.id"), nullable=True)
    scooter_unit_id     = Column(String, ForeignKey("scooter_units.id"), nullable=True)
    dealer_id           = Column(String, ForeignKey("dealers.id"), nullable=True)
    part_name_free      = Column(String(300), nullable=True)
    quantity            = Column(Integer, default=1)
    root_cause          = Column(Text)
    corrective_action   = Column(Text)
    financial_impact    = Column(Float, default=0.0)
    reported_by         = Column(String, ForeignKey("users.id"))
    created_at          = Column(DateTime(timezone=True), server_default=func.now())


# ── AUDIT LOG ─────────────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id         = Column(String, primary_key=True, default=gen_uuid)
    user_id    = Column(String, ForeignKey("users.id"))
    action     = Column(String(100), nullable=False)
    module     = Column(String(50))
    record_id  = Column(String)
    old_value  = Column(Text)
    new_value  = Column(Text)
    ip_address = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class InventoryLocationStock(Base):
    __tablename__ = "inventory_location_stock"

    id          = Column(String, primary_key=True, default=gen_uuid)
    item_id     = Column(String, ForeignKey("inventory_items.id"), nullable=False)
    location_id = Column(String, ForeignKey("locations.id"),       nullable=False)
    quantity    = Column(Integer, default=0)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), onupdate=func.now())

    item     = relationship("InventoryItem", foreign_keys=[item_id])
    location = relationship("Location",      foreign_keys=[location_id])