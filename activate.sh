echo "Ativando ambiente virtual..."

if [ ! -d "venv" ]; then
    echo "Erro: Ambiente virtual não encontrado!"
    echo "Execute: python3 -m venv venv"
    exit 1
fi

source venv/bin/activate

if [ "$VIRTUAL_ENV" != "" ]; then
    echo "Ambiente virtual ativado com sucesso!"
    echo "Localização: $VIRTUAL_ENV"
else
    echo "Erro: Falha ao ativar o ambiente virtual!"
    exit 1
fi
