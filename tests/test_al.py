from bckg import al


def test_strip_comments_keeps_strings_and_quoted_names():
    code = al.strip_comments("x := 'a // b'; // gone\ny := \"Sales // Header\"; /* gone\nstill gone */ z;")
    assert "'a // b'" in code
    assert '"Sales // Header"' in code
    assert 'gone' not in code
    assert code.count('\n') == 2


def test_strip_comments_handles_doubled_quotes():
    assert al.strip_comments("Message('It''s // kept'); // dropped") == "Message('It''s // kept'); "


def test_header_with_quoted_name_extends_and_namespace():
    obj = al.parse('namespace A.B;\n\ntableextension 50000 "ALP Customer" extends Customer\n{\n}\n')
    assert (obj['type'], obj['id'], obj['name'], obj['namespace']) == ('TableExtension', 50000, 'ALP Customer', 'A.B')
    assert obj['extends'] == ('Table', 'Customer')


def test_interface_has_no_id_and_implements_is_split():
    assert al.parse('interface "ALP IThing"\n{\n}\n')['id'] is None
    obj = al.parse('codeunit 50010 "X" implements "ALP IOne", IOther\n{\n}\n')
    assert obj['implements'] == ['ALP IOne', 'IOther']


def test_file_without_object_returns_none():
    assert al.parse('// only a comment\n') is None


def test_table_fields():
    obj = al.parse('table 50001 "W"\n{\n fields\n {\n  field(1; Code; Code[20]) { }\n'
                   '  field(2; "My Text"; Text[100]) { Caption = \'x\'; }\n }\n}\n')
    assert obj['fields'] == [{'id': 1, 'name': 'Code', 'data_type': 'Code[20]'},
                             {'id': 2, 'name': 'My Text', 'data_type': 'Text[100]'}]


def test_api_page_fields_resolve_rec_sources_only():
    obj = al.parse('page 50002 "P"\n{\n PageType = API;\n SourceTable = "ALP Widget";\n layout {\n'
                   '  field(code; Rec.Code) { }\n  field(desc; Rec."Long Description") { }\n'
                   '  field(calc; Something) { }\n }\n}\n')
    assert obj['api_fields'] == [
        {'name': 'code', 'table': 'ALP Widget', 'field': 'Code'},
        {'name': 'desc', 'table': 'ALP Widget', 'field': 'Long Description'},
        {'name': 'calc', 'table': None, 'field': None},
    ]
    assert ('Table', 'ALP Widget') in obj['references']


def test_api_query_columns_belong_to_their_dataitem():
    obj = al.parse('query 50003 "Q"\n{\n QueryType = API;\n elements {\n  dataitem(item; Item) {\n'
                   '   column(no; "No.") { }\n   dataitem(cat; "Item Category") { column(cat; Code) { } }\n'
                   '  }\n }\n}\n')
    assert obj['api_fields'] == [{'name': 'no', 'table': 'Item', 'field': 'No.'},
                                 {'name': 'cat', 'table': 'Item Category', 'field': 'Code'}]


def test_event_subscribers_both_syntaxes_and_trigger_element():
    obj = al.parse('''codeunit 50000 "S"
{
    [EventSubscriber(ObjectType::Codeunit, Codeunit::"Sales-Post", OnAfterPostSalesDoc, '', false, false)]
    local procedure A() begin end;

    [EventSubscriber(ObjectType::Table, Database::Customer, 'OnAfterValidateEvent', 'Name', false, false)]
    local procedure B() begin end;

    [EventSubscriber(ObjectType::Codeunit, Codeunit::"Sales-Post", OnBeforePostSalesDoc, 'Ignored', false, false)]
    procedure C() begin end;
}
''')
    assert obj['subscriptions'] == [
        {'object': ('Codeunit', 'Sales-Post'), 'event': 'OnAfterPostSalesDoc', 'element': '', 'procedure': 'A'},
        {'object': ('Table', 'Customer'), 'event': 'OnAfterValidateEvent', 'element': 'Name', 'procedure': 'B'},
        {'object': ('Codeunit', 'Sales-Post'), 'event': 'OnBeforePostSalesDoc', 'element': '', 'procedure': 'C'},
    ]
    assert ('Codeunit', 'Sales-Post') not in obj['references']


def test_publishers_and_tests():
    obj = al.parse('''codeunit 60000 "T"
{
    Subtype = Test;

    [IntegrationEvent(false, false)]
    local procedure OnSomething(No: Code[20]) begin end;

    [Test]
    [HandlerFunctions('H')]
    procedure FirstTest() begin end;

    procedure Helper() begin end;
}
''')
    assert obj['publishers'] == [{'event': 'OnSomething', 'kind': 'IntegrationEvent'}]
    assert obj['tests'] == ['FirstTest']


def test_references_from_variables_and_type_literals_ignore_comments():
    obj = al.parse('''codeunit 50000 "R"
{
    procedure X()
    var
        Cust: Record Customer;
        Post: Codeunit "Sales-Post";
        Card: TestPage "Customer Card";
    begin
        Page.Run(Page::"Item Card");
        // Codeunit::"Ghost"
        if Cust.Get() then;
        exit(Enum::"Sales Document Type"::Order);
    end;
}
''')
    assert obj['references'] == {('Table', 'Customer'), ('Codeunit', 'Sales-Post'), ('Page', 'Customer Card'),
                                 ('Page', 'Item Card'), ('Enum', 'Sales Document Type')}


def test_dotted_string_literals_are_kept_for_channel_matching():
    obj = al.parse("codeunit 1 \"L\"\n{\n procedure C(): Text begin exit('catalogue.item.changed'); "
                   "Message('Not a channel.'); end;\n}\n")
    assert obj['literals'] == {'catalogue.item.changed'}
