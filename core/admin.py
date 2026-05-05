from django.contrib import admin, messages
from django.utils.safestring import mark_safe
from decimal import Decimal
from .models import (
    CustomUser, 
    PlatformSettings, 
    Level, 
    BankDetails, 
    Deposit, 
    Withdrawal, 
    Task, 
    Roulette, 
    RouletteSettings, 
    UserLevel, 
    PlatformBankDetails
)

@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('phone_number', 'available_balance', 'subsidy_balance', 'is_staff', 'is_active', 'date_joined', 'roulette_spins')
    search_fields = ('phone_number', 'invite_code')
    list_filter = ('is_staff', 'is_active', 'level_active')

@admin.register(PlatformSettings)
class PlatformSettingsAdmin(admin.ModelAdmin):
    list_display = ('id', 'whatsapp_link', 'history_text', 'deposit_instruction', 'withdrawal_instruction')
    search_fields = ('whatsapp_link',)

@admin.register(Level)
class LevelAdmin(admin.ModelAdmin):
    list_display = ('name', 'deposit_value', 'daily_gain', 'monthly_gain', 'cycle_days')
    search_fields = ('name',)

@admin.register(BankDetails)
class BankDetailsAdmin(admin.ModelAdmin):
    list_display = ('user', 'bank_name', 'account_holder_name')
    search_fields = ('user__phone_number', 'bank_name', 'account_holder_name')

@admin.register(PlatformBankDetails)
class PlatformBankDetailsAdmin(admin.ModelAdmin):
    list_display = ('get_type_icon', 'type', 'bank_name', 'account_holder_name', 'IBAN_preview')
    list_filter = ('type', 'bank_name')
    search_fields = ('bank_name', 'account_holder_name', 'IBAN')
    
    fieldsets = (
        ('Configuração de Destino', {
            'fields': ('type',),
            'description': 'Selecione se esta entrada é para pagamentos PIX ou Cripto USDT.'
        }),
        ('Dados da Conta / Carteira', {
            'fields': ('bank_name', 'account_holder_name', 'IBAN'),
        }),
    )

    def get_type_icon(self, obj):
        if obj.type == 'PIX':
            return mark_safe('<span style="color: #32BCAD; font-weight: bold;">💎 PIX</span>')
        return mark_safe('<span style="color: #F3BA2F; font-weight: bold;">🪙 USDT</span>')
    
    get_type_icon.short_description = 'Tipo'

    def IBAN_preview(self, obj):
        if obj.IBAN:
            return obj.IBAN[:20] + "..." if len(obj.IBAN) > 20 else obj.IBAN
        return "-"
    
    IBAN_preview.short_description = 'Chave / Endereço'

    class Media:
        css = {
            'all': ('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css',)
        }

@admin.register(Deposit)
class DepositAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'is_approved', 'created_at', 'proof_link') 
    search_fields = ('user__phone_number',)
    list_filter = ('is_approved',)
    readonly_fields = ('current_proof_display',)

    # LOGICA SOLICITADA: SOMA SALDO AUTOMATICAMENTE AO APROVAR
    def save_model(self, request, obj, form, change):
        if change:
            old_deposit = Deposit.objects.get(pk=obj.pk)
            if not old_deposit.is_approved and obj.is_approved:
                user = obj.user
                user.available_balance += obj.amount
                user.save()
                messages.success(request, f"Saldo de {obj.amount} creditado para {user.phone_number}")
        super().save_model(request, obj, form, change)

    def proof_link(self, obj):
        if obj.proof_of_payment:
            return mark_safe(f'<a href="{obj.proof_of_payment.url}" target="_blank">Ver Comprovativo</a>')
        return "Nenhum"
        
    proof_link.short_description = 'Comprovativo'

    def current_proof_display(self, obj):
        if obj.proof_of_payment:
            return mark_safe(f'''
                <a href="{obj.proof_of_payment.url}" target="_blank">Ver Imagem em Tamanho Real</a><br/>
                <img src="{obj.proof_of_payment.url}" style="max-width:300px; height:auto; margin-top: 10px;" />
            ''')
        return "Nenhum Comprovativo Carregado"
    
    current_proof_display.short_description = 'Comprovativo Atual'

@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    # LOGICA SOLICITADA: DADOS BANCARIOS E BOTAO RÁPIDO NA LISTA
    list_display = (
        'user', 
        'get_dados_bancarios', 
        'get_pagamento_real_brl', 
        'status', 
        'created_at',
        'botao_aprovar_rapido'
    )

    readonly_fields = (
        'get_valor_solicitado_bruto', 
        'get_taxa_descontada', 
        'get_valor_liquido_usdt', 
        'get_pagamento_real_brl',
        'get_dados_bancarios',
        'created_at'
    )

    fieldsets = (
        ('Informações do Usuário', {
            'fields': ('user', 'status')
        }),
        ('Cálculos do Saque (Automático)', {
            'fields': (
                'get_valor_solicitado_bruto', 
                'get_taxa_descontada', 
                'get_valor_liquido_usdt', 
                'get_pagamento_real_brl'
            )
        }),
        ('Coordenadas de Pagamento', {
            'fields': ('get_dados_bancarios',)
        }),
        ('Dados Brutos do Sistema', {
            'fields': ('amount', 'created_at'),
            'classes': ('collapse',),
        }),
    )
    
    CAMBIO_FIXO = Decimal('5.48')
    TAXA = Decimal('0.10') # 10%

    def get_valor_solicitado_bruto(self, obj):
        return f"{obj.amount:.2f} USDT"
    get_valor_solicitado_bruto.short_description = 'Solicitado (Bruto)'

    def get_taxa_descontada(self, obj):
        taxa = obj.amount * self.TAXA
        return f"- {taxa:.2f} USDT"
    get_taxa_descontada.short_description = 'Taxa (10%)'

    def get_valor_liquido_usdt(self, obj):
        liquido = obj.amount * (Decimal('1') - self.TAXA)
        return f"{liquido:.2f} USDT"
    get_valor_liquido_usdt.short_description = 'Líquido (USDT)'

    def get_pagamento_real_brl(self, obj):
        liquido = obj.amount * (Decimal('1') - self.TAXA)
        valor_brl = liquido * self.CAMBIO_FIXO
        return mark_safe(f'<b style="color: #28a745; font-size: 1.2em;">R$ {valor_brl:.2f}</b>')
    get_pagamento_real_brl.short_description = 'VALOR PARA PAGAR (PIX)'

    def get_dados_bancarios(self, obj):
        try:
            dados = BankDetails.objects.get(user=obj.user)
            return mark_safe(
                f"<div style='background:#f0f0f0; padding:8px; border-radius:5px; border-left:5px solid #ffb800;'>"
                f"<b>Titular:</b> {dados.account_holder_name}<br>"
                f"<b>Banco/Rede:</b> {dados.bank_name}<br>"
                f"<b>Chave/Endereço:</b> <code style='background:#fff; padding:2px; border:1px solid #ccc;'>{dados.IBAN}</code>"
                f"</div>"
            )
        except BankDetails.DoesNotExist:
            return mark_safe("<span style='color:red;'>⚠️ Dados não cadastrados</span>")
    get_dados_bancarios.short_description = 'Coordenadas para Pagamento'

    def botao_aprovar_rapido(self, obj):
        if obj.status != 'Aprovado':
            return mark_safe(f'<a class="button" href="?set_status=Aprovado&idx={obj.id}" style="background:#28a745; color:white;">✔ Aprovar</a>')
        return mark_safe("<span style='color:green; font-weight:bold;'>Pago</span>")
    botao_aprovar_rapido.short_description = 'Ação Rápida'

    def changelist_view(self, request, extra_context=None):
        if 'set_status' in request.GET and 'idx' in request.GET:
            Withdrawal.objects.filter(id=request.GET.get('idx')).update(status='Aprovado')
            self.message_user(request, "Saque atualizado com sucesso!")
        return super().changelist_view(request, extra_context)

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('user', 'earnings', 'completed_at')
    search_fields = ('user__phone_number',)

@admin.register(Roulette)
class RouletteAdmin(admin.ModelAdmin):
    list_display = ('user', 'prize', 'is_approved', 'spin_date')
    search_fields = ('user__phone_number',)
    list_filter = ('is_approved',)

@admin.register(RouletteSettings)
class RouletteSettingsAdmin(admin.ModelAdmin):
    list_display = ('id', 'prizes')

@admin.register(UserLevel)
class UserLevelAdmin(admin.ModelAdmin):
    list_display = ('user', 'level', 'purchase_date', 'is_active')
    search_fields = ('user__phone_number', 'level__name')
    list_filter = ('is_active',)
    